# OKF Wealth AI

OKF Wealth AI is a local reference stack for answering wealth-management
questions with Google OKF-style markdown instructions, Frictionless Data
resources, FastAPI, FastMCP, Pydantic AI, and durable agent memory.

The stack is split into three services:

```text
okf_wealth_ai/
├── okf_domain/   # PostgreSQL wealth data and agent-memory databases
├── okf_mcp/      # Frictionless datapackage executor, FastAPI, and FastMCP
└── okf_agent/    # Pydantic AI agent with pydantic-ai-harness memory
```

## What It Does

- Starts a seeded PostgreSQL wealth database on `localhost:5432`.
- Starts a separate PostgreSQL database for long-term agent memory on
  `localhost:5433`.
- Reads the published Frictionless datapackage from GitHub.
- Exposes REST endpoints and MCP tools from `okf_mcp`.
- Reads OKF markdown instructions from the knowledge index before answering.
- Forces scenario-specific instruction reads for holding and redemption
  questions.
- Stores app-level interaction memory in `agent_memory` with operation receipts
  in `agent_memory_operations`.

## Prerequisites

- Docker with Compose
- `uv`
- An OpenAI API key for the default `openai:gpt-5-mini` model

## Quick Start

Start PostgreSQL services:

```bash
cd okf_wealth_ai/okf_domain
docker compose -f compose.yaml up -d
```

Configure the agent:

```bash
cd ../okf_agent
cp .env.example .env
```

Edit `.env` and set:

```text
OPENAI_API_KEY=...
```

Start the API and MCP server in a separate terminal:

```bash
cd okf_wealth_ai/okf_mcp
uv sync
OKF_LOG_LEVEL=INFO uv run okf-api
```

Run the agent:

```bash
cd okf_wealth_ai/okf_agent
uv sync
uv run okf-agent \
  "Show transactions for customer 2 and list the holdings and optimize redemptions" \
  --json
```

## API And MCP

`okf_mcp` serves FastAPI at:

```text
http://127.0.0.1:8000
```

FastMCP is mounted at:

```text
http://127.0.0.1:8000/mcp/
```

Useful REST checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/resources
curl "http://127.0.0.1:8000/customers/2/transactions"
curl "http://127.0.0.1:8000/instructions?include_linked=false"
```

The `/instructions` endpoint should return links to:

```text
holding_calculation.md
redemption_optimizer.md
```

## Agent Runtime Configuration

`okf_agent/.env` is loaded automatically. Shell environment variables override
values in `.env`.

Important settings:

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI provider credential | required |
| `OKF_AGENT_MODEL` | Pydantic AI model id | `openai:gpt-5-mini` |
| `OKF_MCP_URL` | MCP endpoint | `http://127.0.0.1:8000/mcp/` |
| `OKF_API_BASE_URL` | REST API base URL | `http://127.0.0.1:8000` |
| `OKF_AGENT_MEMORY_DSN` | Agent memory Postgres DSN | `postgresql://okf_agent:okf_agent_password@127.0.0.1:5433/okf_agent_memory` |
| `OKF_AGENT_RUN_TIMEOUT_SECONDS` | Full run timeout | `180` |
| `OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS` | One model request timeout | `60` |
| `OKF_AGENT_MAX_MODEL_REQUESTS` | Model calls per run | `8` |
| `OKF_AGENT_MAX_TOOL_CALLS` | Tool calls per run | `16` |
| `OKF_AGENT_MAX_OUTPUT_TOKENS` | Max response tokens | `4000` |
| `OKF_AGENT_LOG_LEVEL` | Agent logging level | `INFO` |

For faster failure while debugging:

```bash
OKF_AGENT_RUN_TIMEOUT_SECONDS=60 \
OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS=20 \
uv run okf-agent "Show transactions for customer 2" --json
```

If the provider reports that the model token limit was exceeded before a
response was generated, raise `OKF_AGENT_MAX_OUTPUT_TOKENS` in `.env`.

## Memory Verification

The memory database is `okf_agent_memory` in container
`okf-agent-memory-postgres`. `pydantic-ai-harness` creates memory tables lazily,
so tables appear after the first agent or memory write.

Every agent run writes an app-level interaction record before the model call:

```text
<session-id>/okf_agent/INTERACTIONS.md
```

Prompts that start with `remember ...` also write:

```text
<session-id>/okf_agent/MEMORY.md
```

Verify content and operation receipts:

```bash
docker exec okf-agent-memory-postgres \
  psql -U okf_agent -d okf_agent_memory \
  -c "select path, left(content, 160), version, last_operation_id from agent_memory order by path limit 10;"

docker exec okf-agent-memory-postgres \
  psql -U okf_agent -d okf_agent_memory \
  -c "select id, version, existed, completed from agent_memory_operations order by id limit 10;"
```

`agent_memory` is the content table. `agent_memory_operations` is the
idempotency receipt table populated by harness `MemoryOperation` writes.

## Tests

Run all component tests:

```bash
cd okf_wealth_ai/okf_mcp
uv run okf-test

cd ../okf_agent
uv run okf-agent-test
```

Compile checks:

```bash
cd okf_wealth_ai/okf_mcp
uv run python -m compileall src tests

cd ../okf_agent
uv run python -m compileall src tests main.py
```

## Troubleshooting

If the agent hangs after local tool calls, check model-provider logs. The agent
now has run and model-request timeouts, but provider retries can still consume
the configured timeout window.

If memory tables are empty, confirm that an agent command has actually run
against the same DSN as the database you are querying:

```bash
cd okf_wealth_ai/okf_agent
uv run okf-agent "Remember that I prefer concise portfolio answers." \
  --session-id memory-check
```

Then query for `memory-check/%` in `agent_memory`.

If `/mcp/` calls fail, make sure `okf_mcp` is running and that
`OKF_MCP_URL=http://127.0.0.1:8000/mcp/` is set in `okf_agent/.env`.
