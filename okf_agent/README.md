# okf-agent

Pydantic AI agent for the OKF wealth management knowledge base.

The agent uses:

- `pydantic-ai-slim[mcp,openai]` for the typed agent runtime and MCP client.
- `pydantic-ai-harness` `Memory(PostgresMemoryStore(...))` for durable memory.
- `http://127.0.0.1:8000/mcp/` for OKF datapackage tools exposed by `okf_exec`.
- `GET /instructions` on the same OKF API server to read the OKF markdown index
  and linked instruction documents before answering.

Start dependencies:

```bash
cd ../okf_domain
docker compose -f compose.yaml up -d

cd ../okf_exec
uv run okf-api
```

Run the agent:

```bash
cd ../okf_agent
uv sync
uv run okf-agent "Show transactions for customer 1 and explain the relevant OKF rule" --json
```

The agent is bounded so provider retries cannot hang indefinitely. Defaults:

- full run timeout: `180s`
- one model request timeout: `60s`
- model requests per run: `8`
- tool calls per run: `16`

For faster debugging:

```bash
OKF_AGENT_RUN_TIMEOUT_SECONDS=60 \
OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS=20 \
OKF_AGENT_MAX_MODEL_REQUESTS=6 \
uv run okf-agent "Show transactions for customer 2 and list holdings and optimize redemptions" --json
```

Enable logs while verifying instruction routing:

```bash
OKF_AGENT_LOG_LEVEL=INFO uv run okf-agent \
  "Calculate holdings for customer 1" \
  --session-id verify-holding \
  --json
```

The logs should show an index lookup first, followed by a separate
`holding_calculation.md` or `redemption_optimizer.md` lookup when the question
requires those rules.

Configuration:

`okf_agent/.env` is loaded automatically before the agent is built. Values
already exported in the shell take precedence over the file.

Create it from the example file:

```bash
cp .env.example .env
```

Keep secrets only in `.env`; it is git-ignored. Runtime knobs such as output
token limits, request timeouts, and MCP URLs should also live in `.env`.

| Variable | Default |
| --- | --- |
| `OKF_AGENT_MODEL` | `openai:gpt-5-mini` |
| `OKF_MCP_URL` | `http://127.0.0.1:8000/mcp/` |
| `OKF_API_BASE_URL` | `http://127.0.0.1:8000` |
| `OKF_AGENT_MEMORY_DSN` | `postgresql://okf_agent:okf_agent_password@127.0.0.1:5433/okf_agent_memory` |
| `OKF_AGENT_RUN_TIMEOUT_SECONDS` | `180` |
| `OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS` | `60` |
| `OKF_AGENT_MAX_MODEL_REQUESTS` | `8` |
| `OKF_AGENT_MAX_TOOL_CALLS` | `16` |
| `OKF_AGENT_MAX_OUTPUT_TOKENS` | `4000` |
| `OKF_AGENT_LOG_LEVEL` | `INFO` |
| `OPENAI_API_KEY` | Required by the OpenAI model provider unless already exported. |

If you see `Model token limit ... exceeded before any response was generated`,
raise `OKF_AGENT_MAX_OUTPUT_TOKENS` in `.env`, for example:

```text
OKF_AGENT_MAX_OUTPUT_TOKENS=4000
```

Verify memory persistence:

The harness injects existing memory and gives the agent `write_memory`,
`read_memory`, `delete_memory`, and `search_memory` tools. `okf_agent` also
persists a small app-level interaction record at the start of every run in
`INTERACTIONS.md`, so the memory database can be verified even if a provider
request times out. Explicit user requests that start with `remember ...` are
also written to `MEMORY.md`.

```bash
cd ../okf_domain
docker compose -f compose.yaml up -d agent-memory-postgres

cd ../okf_agent
uv run okf-agent "Remember that I prefer concise portfolio answers." \
  --session-id memory-check
uv run okf-agent "Show transactions for customer 2." \
  --session-id memory-check \
  --json
uv run okf-agent "What answer style do I prefer?" \
  --session-id memory-check \
  --json
```

Inspect the persisted harness memory tables:

```bash
docker exec okf-agent-memory-postgres \
  psql -U okf_agent -d okf_agent_memory \
  -c "\dt"

docker exec okf-agent-memory-postgres \
  psql -U okf_agent -d okf_agent_memory \
  -c "select path, left(content, 160), version from agent_memory order by path limit 10;"

docker exec okf-agent-memory-postgres \
  psql -U okf_agent -d okf_agent_memory \
  -c "select id, version, existed, completed from agent_memory_operations order by id limit 10;"
```

For the commands above, expect a row whose path starts with:

```text
memory-check/okf_agent/MEMORY.md
memory-check/okf_agent/INTERACTIONS.md
```

`agent_memory` is the content table. `agent_memory_operations` is the
idempotency receipt table; it is populated when writes pass a harness
`MemoryOperation`, including `write_memory` tool calls and app-level interaction
writes.

Run tests:

```bash
uv run okf-agent-test
```

Run agent coverage:

```bash
uv run coverage run -m unittest discover
uv run coverage report -m
```
