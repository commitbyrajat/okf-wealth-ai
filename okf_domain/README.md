# okf-domain

PostgreSQL domain services for the OKF wealth management examples. Compose
starts the seeded wealth database and a separate Postgres instance for
`okf_agent` long-term memory persistence.

## Contents

```text
okf_domain/
├── compose.yaml                  # Wealth and agent-memory PostgreSQL services
├── data/                         # Seed CSV files mounted into PostgreSQL
│   ├── customers.csv
│   ├── fund_master.csv
│   └── transactions.csv
└── db/init/01_schema.sql         # Tables, indexes, seed COPY commands, views
```

## Database

The wealth database exposes PostgreSQL on `localhost:5432` with these defaults:

| Setting | Value |
| --- | --- |
| Database | `okf_wealth` |
| User | `okf` |
| Password | `okf_password` |
| Container | `okf-postgres` |

The agent memory database is isolated on `localhost:5433`:

| Setting | Value |
| --- | --- |
| Database | `okf_agent_memory` |
| User | `okf_agent` |
| Password | `okf_agent_password` |
| Container | `okf-agent-memory-postgres` |

Start the database from this directory:

```bash
cd okf_domain
docker compose up -d
```

Stop it without deleting the seeded volume:

```bash
docker compose down
```

Reset all database state and replay the init scripts:

```bash
docker compose down -v
docker compose up -d
```

Verify the agent memory database:

```bash
docker exec okf-agent-memory-postgres \
  psql -U okf_agent -d okf_agent_memory \
  -c "\dt"
```

The `pydantic-ai-harness` Postgres memory store creates its tables lazily on the
first agent run, so an empty table list before running `okf_agent` is expected.

## Schema

`db/init/01_schema.sql` creates three base tables:

| Table | Purpose |
| --- | --- |
| `customers` | Customer identity and risk profile data. |
| `fund_master` | Fund metadata, NAV, and exit-load rules. |
| `transactions` | Buy and sell ledger entries by customer and fund. |

It also creates two query views:

| View | Purpose |
| --- | --- |
| `current_holdings` | Aggregates buy and sell transactions into current units, market value, and open/closed status. |
| `redemption_lots` | Lists buy lots with holding period and exit-load eligibility. |

## Frictionless Usage

The execution project reads this database through the PostgreSQL-backed
resources in `okf_base/datapackage.yaml`. That descriptor uses Frictionless SQL
resource configuration for table selection, filters, and ordering.
`okf_base/datapackage.json` mirrors the YAML descriptor for GitHub portal usage.

Run the example after the database is healthy:

```bash
cd okf_exec
uv sync
uv run okf-exec
```

## Maintenance

When changing columns, constraints, seed data, or views, update
`okf_base/datapackage.yaml` and regenerate `okf_base/datapackage.json` at the
same time so the executable examples and Frictionless validation stay aligned
with the database contract.
