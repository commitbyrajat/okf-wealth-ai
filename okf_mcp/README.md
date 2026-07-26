# okf-exec

Executable Python examples for the OKF wealth management knowledge base.

Run after PostgreSQL is started:

```bash
cd okf_exec
uv sync
uv run okf-exec
```

Filter the `transactions_by_customer` resource by customer id:

```bash
uv run okf-exec --customer-id 1
```

The same filter can be provided through `OKF_CUSTOMER_ID`.

Run the unit tests:

```bash
uv run okf-test
```

Run the FastAPI server with FastMCP mounted:

```bash
uv run okf-api
```

The REST API is served from `http://127.0.0.1:8000` by default. FastMCP is
mounted at `http://127.0.0.1:8000/mcp` using `FastMCP.http_app(path="/")` and
FastAPI lifespan integration.

Enable API and MCP logs:

```bash
OKF_LOG_LEVEL=INFO uv run okf-api
```

Instruction logs show the normalized markdown URL and discovered link count,
which makes it clear whether the agent fetched the index only or also fetched
`holding_calculation.md` / `redemption_optimizer.md`.

REST endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | API health check. |
| `GET` | `/resources` | List resources declared in `datapackage.json`. |
| `GET` | `/resources/{resource_name}/schema` | Return schema and SQL dialect metadata for one resource. |
| `GET` | `/resources/{resource_name}/rows?limit_rows=100` | Read rows from any datapackage resource. |
| `GET` | `/customers/{customer_id}/transactions` | Read transactions for one customer through `transactions_by_customer`. |
| `GET` | `/instructions?url=...` | Read an OKF markdown instruction document and return linked markdown documents to read next. |

The instructions endpoint defaults to the published OKF wealth knowledge index:

```text
https://github.com/commitbyrajat/okf-wealth-base/blob/main/knowledge/index.md
```

Set `include_linked=true` to also fetch the markdown files linked by the
requested document. `max_depth` is bounded from `0` to `2` to keep the response
size controlled.

MCP tools:

| Tool | Description |
| --- | --- |
| `list_datapackage_resources` | Lists every resource declared in the OKF wealth management datapackage. |
| `get_resource_schema` | Returns schema and SQL dialect metadata for one resource. |
| `read_resource_rows` | Reads bounded rows from any datapackage resource. |
| `get_customer_transactions` | Filters `transactions_by_customer` by customer id. |

By default the example reads the published package through the Frictionless
GitHub portal from:

```text
https://github.com/commitbyrajat/okf-wealth-base/blob/main/datapackage.json
```

The Frictionless GitHub portal is repository-based, so the implementation loads
`https://github.com/commitbyrajat/okf-wealth-base` and lets Frictionless resolve
the root-level `datapackage.json`.

Before printing example results, the script validates every package resource
with a Frictionless `Checklist`. Baseline checks are included automatically by
Frictionless, and the script adds `checks.table_dimensions` to require at least
one row and the exact field count declared by each resource schema.
Package metadata is validated before resource reads, and Frictionless metadata,
resource, table, row, and cell errors are normalized into readable runtime
messages with resource names where available.

The printed summaries use Frictionless `TableResource`, `transform`, and
`steps` on in-memory extracted rows. The source SQL resources are not mutated;
transforms only shape display rows with row sorting/slicing, field filtering,
field metadata updates, and cell formatting.

The execution code is split by responsibility:

```text
src/okf_exec/
├── example.py             # CLI entry point and backward-compatible facade
├── settings.py            # Package source configuration
├── package_loader.py      # GitHub/local Frictionless package loading
├── validation.py          # Metadata and resource validation
├── errors.py              # Frictionless error formatting
├── package_resources.py   # Resource discovery and extraction helpers
├── transformations.py     # In-memory TableResource transform pipelines
├── instructions.py        # OKF markdown instruction reading and link traversal
└── presentation.py        # Console summary rendering
```

`OKF_DATAPACKAGE_SOURCE` can still be set to another explicit Frictionless
package source when needed.

The `okf-example` script is also available as a compatibility alias.
