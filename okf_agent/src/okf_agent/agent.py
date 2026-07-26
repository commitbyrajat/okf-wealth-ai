from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, AsyncIterator
from urllib.parse import unquote, urlparse

import asyncpg
import httpx
from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness.memory import (
    Memory,
    MemoryConflictError,
    MemoryOperation,
    PostgresMemoryStore,
)

from .config import AgentSettings
from .logging_config import configure_logging
from .models import InstructionDocument, OkfAgentAnswer, OkfAgentDeps


logger = logging.getLogger(__name__)

REMEMBER_PATTERN = re.compile(r"\bremember(?:\s+that)?\s+(?P<note>.+)", re.IGNORECASE)
MEMORY_FILENAME = "MEMORY.md"
INTERACTIONS_FILENAME = "INTERACTIONS.md"
MEMORY_WRITE_ATTEMPTS = 3
MAX_MEMORY_ENTRY_CHARS = 2_000

DEFAULT_INSTRUCTIONS_URL = (
    "https://github.com/commitbyrajat/okf-wealth-base/blob/main/knowledge/index.md"
)


class AgentRunTimeoutError(TimeoutError):
    """Raised when an OKF agent run exceeds its configured wall-clock timeout."""

SYSTEM_PROMPT = """
You are the OKF wealth management agent.

Mandatory workflow:
1. Before producing the final answer, call read_okf_instructions for the default
   OKF knowledge index unless the user explicitly provides another OKF markdown
   URL. Read the index with include_linked=false so it acts as a routing table.
2. Use the index links to decide which scenario applies. Then call
   read_okf_instructions again for every scenario document needed for the final
   answer, especially holding_calculation.md for holding questions and
   redemption_optimizer.md for redemption or exit-load questions.
3. Use the OKF MCP tools from the configured server for datapackage resources,
   schemas, rows, and customer transaction data when factual data is needed.
4. Persistent memory can help with user preferences and prior context, but it
   must not override current OKF markdown instructions or MCP data.
5. Return a typed OkfAgentAnswer through the return_okf_answer output tool.
   Include the index and each separately-read scenario document in both
   instruction_urls and consulted_instructions. For holding, redemption,
   customer transaction, and resource inspection answers, do not produce a
   final answer after reading only the index.
""".strip()


def build_agent(
    settings: AgentSettings | None = None,
    *,
    memory: Memory[OkfAgentDeps] | None = None,
) -> Agent[OkfAgentDeps, OkfAgentAnswer]:
    resolved_settings = settings or AgentSettings()
    capabilities = [memory] if memory is not None else []
    agent = Agent[OkfAgentDeps, OkfAgentAnswer](
        resolved_settings.model,
        deps_type=OkfAgentDeps,
        output_type=ToolOutput(
            OkfAgentAnswer,
            name="return_okf_answer",
            description=(
                "Return the final OKF wealth answer with scenario, consulted "
                "instruction documents, data sources, and assumptions."
            ),
            max_retries=2,
        ),
        system_prompt=SYSTEM_PROMPT,
        toolsets=[
            MCPToolset(
                resolved_settings.mcp_url,
                include_instructions=True,
            )
        ],
        capabilities=capabilities,
        defer_model_check=True,
        retries={"output": 1},
    )

    @agent.tool
    async def read_okf_instructions(
        ctx: RunContext[OkfAgentDeps],
        url: Annotated[
            str,
            Field(
                description=(
                    "HTTP(S) markdown URL to read. Use the default OKF "
                    "knowledge index unless the user provides another URL."
                ),
            ),
        ] = DEFAULT_INSTRUCTIONS_URL,
        include_linked: Annotated[
            bool,
            Field(
                description=(
                    "When true, also read linked markdown documents discovered "
                    "in the requested document."
                ),
            ),
        ] = False,
        max_depth: Annotated[
            int,
            Field(
                ge=0,
                le=2,
                description="Maximum markdown-link traversal depth.",
            ),
        ] = 1,
    ) -> InstructionDocument:
        """Read OKF markdown instructions and the next documents to consult."""

        logger.info(
            "reading OKF instructions url=%s include_linked=%s max_depth=%s",
            url,
            include_linked,
            max_depth,
        )
        try:
            response = await ctx.deps.http_client.get(
                "/instructions",
                params={
                    "url": url,
                    "include_linked": include_linked,
                    "max_depth": max_depth,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exception:
            logger.warning(
                "failed reading OKF instructions url=%s error=%s",
                url,
                exception,
            )
            raise ModelRetry(
                f"Unable to read OKF instructions from {url}: {exception}"
            ) from exception

        document = InstructionDocument.model_validate(response.json())
        ctx.deps.consulted_instruction_urls.add(document.resolved_url)
        logger.info(
            "read OKF instructions resolved_url=%s links=%s",
            document.resolved_url,
            len(document.links),
        )
        return document

    @agent.output_validator
    async def validate_instruction_coverage(
        ctx: RunContext[OkfAgentDeps],
        output: OkfAgentAnswer,
    ) -> OkfAgentAnswer:
        consulted_urls = {
            normalize_instruction_url(url)
            for url in ctx.deps.consulted_instruction_urls
        }
        output_urls = {
            normalize_instruction_url(url)
            for url in output.instruction_urls
        }
        scenario_urls = {
            normalize_instruction_url(instruction.url)
            for instruction in output.consulted_instructions
            if instruction.role == "scenario_rule"
        }

        logger.info(
            "validating OKF answer consulted_tool_urls=%s output_instruction_urls=%s",
            sorted(consulted_urls),
            sorted(output_urls),
        )
        if normalize_instruction_url(DEFAULT_INSTRUCTIONS_URL) not in consulted_urls:
            raise ModelRetry(
                "Read the OKF knowledge index with read_okf_instructions before "
                "returning the final answer."
            )
        requires_scenario_document = output.scenario != "general"
        if requires_scenario_document and not scenario_urls:
            raise ModelRetry(
                "Read the scenario-specific OKF instruction document, then include "
                "it as a scenario_rule in consulted_instructions."
            )
        missing_reads = output_urls - consulted_urls
        if missing_reads:
            raise ModelRetry(
                "Only cite instruction URLs actually read with read_okf_instructions. "
                f"These URLs were cited but not read: {sorted(missing_reads)}"
            )
        default_url = normalize_instruction_url(DEFAULT_INSTRUCTIONS_URL)
        if requires_scenario_document and not any(
            url != default_url for url in consulted_urls
        ):
            raise ModelRetry(
                "The final answer cannot be based on the index alone. Read "
                "holding_calculation.md or redemption_optimizer.md when relevant."
            )
        return output

    return agent


@asynccontextmanager
async def open_memory(settings: AgentSettings) -> AsyncIterator[Memory[OkfAgentDeps]]:
    logger.info(
        "opening OKF agent memory pool dsn=%s",
        mask_dsn(settings.memory_dsn),
    )
    pool = await asyncpg.create_pool(
        settings.memory_dsn,
        min_size=settings.memory_min_size,
        max_size=settings.memory_max_size,
    )
    try:
        yield Memory(
            PostgresMemoryStore(pool),
            agent_name="okf_agent",
            namespace=lambda ctx: ctx.deps.session_id,
            max_tokens=1_500,
            max_lines=120,
        )
    finally:
        await pool.close()
        logger.info("closed OKF agent memory pool")


async def run_question(
    question: str,
    *,
    session_id: str = "default",
    settings: AgentSettings | None = None,
) -> OkfAgentAnswer:
    resolved_settings = settings or AgentSettings()
    configure_logging(resolved_settings.log_level)
    logger.info(
        (
            "starting OKF agent run session_id=%s model=%s mcp_url=%s "
            "api_base_url=%s run_timeout_seconds=%s model_timeout_seconds=%s"
        ),
        session_id,
        resolved_settings.model,
        resolved_settings.mcp_url,
        resolved_settings.api_base_url,
        resolved_settings.run_timeout_seconds,
        resolved_settings.model_request_timeout_seconds,
    )
    try:
        async with asyncio.timeout(resolved_settings.run_timeout_seconds):
            async with (
                httpx.AsyncClient(
                    base_url=resolved_settings.api_base_url,
                    timeout=resolved_settings.request_timeout_seconds,
                ) as http_client,
                open_memory(resolved_settings) as memory,
            ):
                agent = build_agent(resolved_settings, memory=memory)
                deps = OkfAgentDeps(
                    session_id=session_id,
                    http_client=http_client,
                )
                await persist_interaction_start(memory, deps, question)
                await persist_explicit_memory(memory, deps, question)
                async with agent:
                    result = await agent.run(
                        question,
                        deps=deps,
                        model_settings=build_model_settings(resolved_settings),
                        usage_limits=build_usage_limits(resolved_settings),
                    )
                await persist_interaction_result(memory, deps, result.output)
                logger.info(
                    "completed OKF agent run session_id=%s instruction_count=%s",
                    session_id,
                    len(result.output.instruction_urls),
                )
                return result.output
    except TimeoutError as exception:
        logger.error(
            "OKF agent run timed out session_id=%s timeout_seconds=%s",
            session_id,
            resolved_settings.run_timeout_seconds,
        )
        raise AgentRunTimeoutError(
            "OKF agent run timed out after "
            f"{resolved_settings.run_timeout_seconds:.0f}s. "
            "Increase OKF_AGENT_RUN_TIMEOUT_SECONDS or reduce the question scope."
        ) from exception


def build_model_settings(settings: AgentSettings) -> ModelSettings:
    return ModelSettings(
        timeout=settings.model_request_timeout_seconds,
        max_tokens=settings.max_output_tokens,
    )


def build_usage_limits(settings: AgentSettings) -> UsageLimits:
    return UsageLimits(
        request_limit=settings.max_model_requests,
        tool_calls_limit=settings.max_tool_calls,
    )


async def persist_explicit_memory(
    memory: Memory[OkfAgentDeps],
    deps: OkfAgentDeps,
    question: str,
) -> None:
    note = extract_memory_note(question)
    if note is None:
        return

    path = f"{deps.session_id}/okf_agent/{MEMORY_FILENAME}"
    entry = (
        f"\n- {datetime.now(UTC).isoformat(timespec='seconds')}: "
        f"User asked to remember: {note}\n"
    )
    await append_memory_entry(memory, path, entry)
    logger.info("persisted explicit memory path=%s", path)


async def persist_interaction_start(
    memory: Memory[OkfAgentDeps],
    deps: OkfAgentDeps,
    question: str,
) -> None:
    path = f"{deps.session_id}/okf_agent/{INTERACTIONS_FILENAME}"
    entry = (
        f"\n## {datetime.now(UTC).isoformat(timespec='seconds')} run started\n"
        f"- user_prompt: {truncate_memory_text(question)}\n"
    )
    await append_memory_entry(memory, path, entry)
    logger.info("persisted interaction start path=%s", path)


async def persist_interaction_result(
    memory: Memory[OkfAgentDeps],
    deps: OkfAgentDeps,
    answer: OkfAgentAnswer,
) -> None:
    path = f"{deps.session_id}/okf_agent/{INTERACTIONS_FILENAME}"
    entry = (
        f"- scenario: {answer.scenario}\n"
        f"- instruction_urls: {', '.join(answer.instruction_urls)}\n"
        f"- answer_summary: {truncate_memory_text(answer.answer)}\n"
    )
    await append_memory_entry(memory, path, entry)
    logger.info("persisted interaction result path=%s", path)


async def append_memory_entry(
    memory: Memory[OkfAgentDeps],
    path: str,
    entry: str,
) -> None:
    operation = memory_operation("app_append", path, entry)
    for attempt in range(MEMORY_WRITE_ATTEMPTS):
        current = await memory.store.read(path, max_chars=memory.max_memory_size)
        current_content = "" if current is None else current.content
        try:
            await memory.store.write(
                path,
                f"{current_content}{entry}",
                expected_version=None if current is None else current.version,
                operation=operation,
            )
        except MemoryConflictError:
            if attempt + 1 == MEMORY_WRITE_ATTEMPTS:
                raise
            continue

        return


def memory_operation(kind: str, path: str, entry: str) -> MemoryOperation:
    fingerprint = hashlib.sha256(f"{kind}\0{path}\0{entry}".encode()).hexdigest()
    operation_id = f"okf_agent:{kind}:{fingerprint[:32]}"
    return MemoryOperation(id=operation_id, fingerprint=fingerprint)


def truncate_memory_text(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= MAX_MEMORY_ENTRY_CHARS:
        return compact
    return f"{compact[:MAX_MEMORY_ENTRY_CHARS]}..."


def extract_memory_note(text: str) -> str | None:
    match = REMEMBER_PATTERN.search(text.strip())
    if match is None:
        return None

    note = match.group("note").strip()
    return note or None


def normalize_instruction_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc != "github.com":
        return url

    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    if len(segments) < 5 or segments[2] != "blob":
        return url

    owner, repository, _, branch, *path_parts = segments
    path = "/".join(path_parts)
    return f"https://raw.githubusercontent.com/{owner}/{repository}/{branch}/{path}"


def mask_dsn(dsn: str) -> str:
    parsed = urlparse(dsn)
    if not parsed.password:
        return dsn

    username = parsed.username or ""
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    redacted_netloc = f"{username}:***@{hostname}{port}"
    return parsed._replace(netloc=redacted_netloc).geturl()
