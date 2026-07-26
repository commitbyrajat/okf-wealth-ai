from __future__ import annotations

import asyncio
from dataclasses import dataclass
import unittest

from okf_agent.agent import (
    DEFAULT_INSTRUCTIONS_URL,
    SYSTEM_PROMPT,
    build_agent,
    build_model_settings,
    build_usage_limits,
    extract_memory_note,
    mask_dsn,
    normalize_instruction_url,
    persist_explicit_memory,
    persist_interaction_result,
    persist_interaction_start,
)
from okf_agent.config import AgentSettings
from okf_agent.models import InstructionDocument, OkfAgentAnswer, OkfAgentDeps


HOLDING_URL = (
    "https://raw.githubusercontent.com/commitbyrajat/"
    "okf-wealth-base/main/knowledge/holding_calculation.md"
)


class AgentTest(unittest.TestCase):
    def test_system_prompt_requires_instruction_lookup(self) -> None:
        self.assertIn("call read_okf_instructions", SYSTEM_PROMPT)
        self.assertIn("include_linked=false", SYSTEM_PROMPT)
        self.assertIn("holding_calculation.md", SYSTEM_PROMPT)
        self.assertIn("redemption_optimizer.md", SYSTEM_PROMPT)
        self.assertIn("configured server", SYSTEM_PROMPT)
        self.assertIn("Persistent memory", SYSTEM_PROMPT)

    def test_answer_requires_multiple_instruction_urls(self) -> None:
        answer = OkfAgentAnswer(
            scenario="general",
            answer="Only index",
            instruction_urls=[DEFAULT_INSTRUCTIONS_URL],
            consulted_instructions=[
                {
                    "title": "Index",
                    "url": DEFAULT_INSTRUCTIONS_URL,
                    "role": "index",
                    "reason": "Routing",
                }
            ],
        )

        self.assertEqual(answer.scenario, "general")

    def test_answer_requires_scenario_instruction(self) -> None:
        with self.assertRaises(ValueError):
            OkfAgentAnswer(
                scenario="holding_calculation",
                answer="No scenario instruction",
                instruction_urls=[DEFAULT_INSTRUCTIONS_URL, HOLDING_URL],
                consulted_instructions=[
                    {
                        "title": "Index",
                        "url": DEFAULT_INSTRUCTIONS_URL,
                        "role": "index",
                        "reason": "Routing",
                    },
                    {
                        "title": "Holding",
                        "url": HOLDING_URL,
                        "role": "supporting",
                        "reason": "Background",
                    },
                ],
            )

    def test_instruction_document_accepts_linked_documents(self) -> None:
        document = InstructionDocument.model_validate(
            {
                "url": DEFAULT_INSTRUCTIONS_URL,
                "resolved_url": "https://raw.example/index.md",
                "content": "# Index",
                "links": [
                    {
                        "title": "Holding",
                        "url": "holding.md",
                        "resolved_url": "https://raw.example/holding.md",
                    }
                ],
                "linked_documents": [
                    {
                        "url": "https://raw.example/holding.md",
                        "resolved_url": "https://raw.example/holding.md",
                        "content": "# Holding",
                        "links": [],
                    }
                ],
            }
        )

        self.assertEqual(document.links[0].title, "Holding")
        self.assertEqual(document.linked_documents[0].content, "# Holding")

    def test_build_agent_uses_configured_model(self) -> None:
        agent = build_agent(
            AgentSettings(
                model="openai:gpt-5-mini",
                mcp_url="http://127.0.0.1:8000/mcp/",
            )
        )

        self.assertIn("return_okf_answer", repr(agent.output_type))

    def test_build_model_settings_sets_timeout_and_output_limit(self) -> None:
        settings = AgentSettings(
            model_request_timeout_seconds=12,
            max_output_tokens=345,
        )

        model_settings = build_model_settings(settings)

        self.assertEqual(model_settings["timeout"], 12)
        self.assertEqual(model_settings["max_tokens"], 345)

    def test_build_usage_limits_sets_request_and_tool_limits(self) -> None:
        settings = AgentSettings(max_model_requests=4, max_tool_calls=9)

        usage_limits = build_usage_limits(settings)

        self.assertEqual(usage_limits.request_limit, 4)
        self.assertEqual(usage_limits.tool_calls_limit, 9)

    def test_normalizes_instruction_urls(self) -> None:
        self.assertEqual(
            normalize_instruction_url(
                "https://github.com/commitbyrajat/"
                "okf-wealth-base/blob/main/knowledge/index.md"
            ),
            (
                "https://raw.githubusercontent.com/commitbyrajat/"
                "okf-wealth-base/main/knowledge/index.md"
            ),
        )

    def test_mask_dsn_hides_password(self) -> None:
        self.assertEqual(
            mask_dsn(
                "postgresql://okf_agent:okf_agent_password@127.0.0.1:5433/"
                "okf_agent_memory"
            ),
            "postgresql://okf_agent:***@127.0.0.1:5433/okf_agent_memory",
        )

    def test_extract_memory_note(self) -> None:
        self.assertEqual(
            extract_memory_note("Remember that I prefer concise answers."),
            "I prefer concise answers.",
        )
        self.assertIsNone(extract_memory_note("Calculate holdings for customer 1."))

    def test_persist_explicit_memory_appends_to_main_notebook(self) -> None:
        async def run() -> str:
            store = FakeMemoryStore()
            memory = FakeMemory(store=store)
            deps = OkfAgentDeps(session_id="memory-check", http_client=None)

            await persist_explicit_memory(
                memory,
                deps,
                "Remember that I prefer concise answers.",
            )
            await persist_explicit_memory(
                memory,
                deps,
                "Remember that I prefer INR amounts.",
            )
            return store.rows["memory-check/okf_agent/MEMORY.md"].content

        content = asyncio.run(run())

        self.assertIn("I prefer concise answers.", content)
        self.assertIn("I prefer INR amounts.", content)

    def test_persist_interaction_start_writes_before_model_result(self) -> None:
        async def run() -> str:
            store = FakeMemoryStore()
            memory = FakeMemory(store=store)
            deps = OkfAgentDeps(session_id="default", http_client=None)

            await persist_interaction_start(
                memory,
                deps,
                "Show transactions for customer 2.",
            )
            return store.rows["default/okf_agent/INTERACTIONS.md"].content

        content = asyncio.run(run())

        self.assertIn("run started", content)
        self.assertIn("Show transactions for customer 2.", content)

    def test_app_memory_writes_create_operation_receipts(self) -> None:
        async def run() -> list[str]:
            store = FakeMemoryStore()
            memory = FakeMemory(store=store)
            deps = OkfAgentDeps(session_id="default", http_client=None)

            await persist_interaction_start(
                memory,
                deps,
                "Show transactions for customer 2.",
            )
            return [operation.id for operation in store.operations]

        operation_ids = asyncio.run(run())

        self.assertEqual(len(operation_ids), 1)
        self.assertTrue(operation_ids[0].startswith("okf_agent:app_append:"))


    def test_persist_interaction_result_appends_answer_summary(self) -> None:
        async def run() -> str:
            store = FakeMemoryStore()
            memory = FakeMemory(store=store)
            deps = OkfAgentDeps(session_id="default", http_client=None)
            answer = OkfAgentAnswer(
                scenario="general",
                answer="Use concise portfolio answers.",
                instruction_urls=[DEFAULT_INSTRUCTIONS_URL],
                consulted_instructions=[
                    {
                        "title": "Index",
                        "url": DEFAULT_INSTRUCTIONS_URL,
                        "role": "index",
                        "reason": "Routing",
                    }
                ],
            )

            await persist_interaction_result(memory, deps, answer)
            return store.rows["default/okf_agent/INTERACTIONS.md"].content

        content = asyncio.run(run())

        self.assertIn("scenario: general", content)
        self.assertIn("Use concise portfolio answers.", content)


@dataclass
class FakeMemoryFile:
    content: str
    version: str


class FakeMemoryStore:
    def __init__(self) -> None:
        self.rows: dict[str, FakeMemoryFile] = {}
        self.operations = []

    async def read(self, path: str, *, max_chars: int):
        return self.rows.get(path)

    async def write(self, path: str, content: str, *, expected_version, operation=None):
        if operation is not None:
            self.operations.append(operation)
        version = str(int(self.rows.get(path, FakeMemoryFile("", "0")).version) + 1)
        self.rows[path] = FakeMemoryFile(content=content, version=version)
        return object()


@dataclass
class FakeMemory:
    store: FakeMemoryStore
    max_memory_size: int = 65_536


if __name__ == "__main__":
    unittest.main()
