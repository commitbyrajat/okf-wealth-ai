# Building an OKF Powered Redemption Optimizer with Frictionless and Pydantic AI Harness

## A field note from turning markdown knowledge, datapackages, MCP tools, and agent memory into one working flow

The first version of this system looked simple on paper.

Ask an agent:

```bash
uv run okf-agent "Show transactions for customer 2 and list the holdings and optimize redemptions" --json | jq
```

The agent should fetch customer transactions, calculate current holdings, apply redemption rules, and recommend which fund lots to redeem first.

That sounds like a normal agent demo until the answer has to be defensible.

For a wealth-management use case, an answer is not good enough because it sounds right. It has to say which data it used, which rule document it read, how it interpreted buys and sells, and why one redemption path is better than another.

That pushed the design away from “chat over data” and toward something stricter:

- Frictionless Data for the data contract
- OKF-style markdown for business knowledge
- FastAPI and FastMCP for executable access
- Pydantic AI for structured agent behavior
- Pydantic AI Harness with PostgreSQL for durable memory


![](.MEDIUM_images/dc5cce02.png)

---

## Why Redemption Optimization Needs More Than a Chatbot

The use case was narrow by design: help a wealth customer decide what to redeem.

The agent needed to answer questions like:

> Show transactions for customer 2 and list the holdings and optimize redemptions.

The expected answer was not a paragraph. It had to include:

- the customer’s transaction rows
- fund metadata
- current units by fund
- NAV-based current value
- holding period
- exit-load status
- FIFO ordering
- a practical redemption recommendation

The final run produced exactly that kind of answer. For customer `2`, the agent found three buy transactions. It calculated 80 units in fund `502`, 125 units in fund `504`, and a total portfolio value of `4526.00` based on the NAVs present in the data.

It then recommended redeeming fund `504` first because that lot was outside its exit-load window. Fund `502` lots were still inside the 365-day exit-load period.

That final answer was useful. Getting there took several iterations.

The main lesson was this: the agent should not be the source of truth. It should be the coordinator.

---

## Helping Wealth Customers Redeem the Right Fund Lots

Redemption optimization is deceptively easy to explain.

A customer owns units across one or more funds. Some units are old enough to redeem without exit load. Some are not. A good system should avoid unnecessary exit load, follow the business rule for lot ordering, and still give the user a practical answer.

For the customer in the implementation run, the data looked like this:

- Fund `504`, Balanced Advantage Fund: `125` units bought on `2025-11-15`. The exit-load rule is `180` days at `1.00` rate. In the captured run, no exit load applied.
- Fund `502`, Short Duration Debt Fund: `50` units bought on `2026-02-01`. The exit-load rule is `365` days at `0.50` rate. In the captured run, exit load applied.
- Fund `502`, Short Duration Debt Fund: `30` units bought on `2026-04-05`. The same `365` day, `0.50` rate exit-load rule applied.

The agent’s recommendation was direct:

> Prefer redeeming from lots with no exit load first. That makes the Balanced Advantage Fund (fund 504, 125 units) the top candidate because its holding period (253 days) exceeds the 180-day exit-load window.

The answer also gave a practical boundary. Redeem up to `3550.00`, or up to `125` units, from fund `504` first. If the customer needs more, then start touching fund `502`, where exit load applies.

That is the kind of answer an advisor can work with.

---

## Knowledge Sources Behind This Implementation

The design was based on four public sources and one implementation repository.

Open Knowledge Foundation, at https://okfn.org/en/, shaped the broader idea that useful knowledge should be accessible, shareable, and reusable.

The Frictionless Data Package specification, at https://specs.frictionlessdata.io/#what-s-a-data-package, shaped the data contract model: package, resources, schema, and machine-readable metadata.

The Google Open Knowledge Format spec, at https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md, shaped the idea of treating each business rule as a Concept document: one markdown file with frontmatter and a structured body.

The Google Cloud OKF article, at https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing, shaped the framing that knowledge sharing needs a format, not just documents scattered in repositories.

The wealth OKF base repository, at https://github.com/commitbyrajat/okf-wealth-base, became the actual knowledge base and datapackage contract consumed by the agent.

Those sources influenced one important decision.

The business rules were not embedded only in code. They lived as markdown knowledge documents, and the agent had to read them at runtime before answering.

The implementation repository has two important parts:

`knowledge/index.md` is the OKF directory listing. It routes scenarios to the right concept documents.

`knowledge/holding_calculation.md` is an OKF Concept document with `type: "logic_doc"`. It defines the holding calculation rule: buys add units, sells subtract units, and non-positive totals are closed holdings.

`knowledge/redemption_optimizer.md` is an OKF Concept document with `type: "strategy_doc"`. It defines the redemption policy: prefer FIFO, avoid exit-load lots where the holding period is still inside the exit-load window, and handle partial redemption differently from full redemption.

`datapackage.json` is the Frictionless contract for SQL-backed resources such as `customers`, `fund_master`, `transactions`, `transactions_by_customer`, `current_holdings`, `redemption_lots`, `open_holdings`, and `exit_load_free_redemption_lots`.

The OKF spec makes a useful distinction here. A Concept is a single unit of knowledge represented as one markdown document. `index.md` is reserved for directory listing and progressive disclosure. The other markdown files are concept documents. That is why `holding_calculation.md` and `redemption_optimizer.md` are not just supporting notes. They are the business-rule units the agent must consult.

That gave the implementation two layers of contract:

- data contracts through Frictionless Data
- knowledge contracts through OKF-style markdown

---

## From Domain-Owned Open Knowledge to Executable Knowledge Contracts

Documents are useful until the system ignores them.

That is the failure mode I wanted to avoid. If the holding logic was written in a markdown file, the agent had to prove it read that file. If the redemption optimizer had a separate markdown rule, the agent had to read that too.

There is a second failure mode that matters more in a retail bank: the wrong people own the rule.

Redemption logic is not only a software concern. Product teams understand fund behavior. Advisory teams understand customer conversations. Operations teams know settlement and servicing constraints. Risk and compliance teams know what the bank can safely say. Engineering should make the rules executable, but the domain experts should be able to read, review, and maintain the knowledge base.

That is why putting the OKF knowledge base in `https://github.com/commitbyrajat/okf-wealth-base` matters. A markdown file in Git can go through pull requests, review comments, approvals, and history. A rule hidden inside an agent prompt or a Python function is much harder for a non-engineering reviewer to challenge.

The logs became part of the design.

For the redemption optimizer run, the agent first read the index:

```text
2026-07-27 01:19:04,793 INFO okf_agent.agent reading OKF instructions url=https://github.com/commitbyrajat/okf-wealth-base/blob/main/knowledge/index.md include_linked=False max_depth=1
2026-07-27 01:19:04,818 INFO okf_agent.agent read OKF instructions resolved_url=https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/index.md links=2
```

Then it read the holding rule:

```text
2026-07-27 01:19:10,724 INFO okf_agent.agent reading OKF instructions url=https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/holding_calculation.md include_linked=False max_depth=1
2026-07-27 01:19:10,750 INFO okf_agent.agent read OKF instructions resolved_url=https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/holding_calculation.md links=0
```

Then it read the redemption rule:

```text
2026-07-27 01:19:20,046 INFO okf_agent.agent reading OKF instructions url=https://github.com/commitbyrajat/okf-wealth-base/blob/main/knowledge/redemption_optimizer.md include_linked=False max_depth=1
2026-07-27 01:19:20,401 INFO okf_agent.agent read OKF instructions resolved_url=https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/redemption_optimizer.md links=0
```

That sequence matters. The index routed the request. The scenario files supplied the rules.

---

## What Is OKF and Why It Fits This Use Case

I used OKF as a lightweight way to organize operational knowledge.

The project had an index document and scenario documents. The index did not answer the business question by itself. It told the agent which document to read next.

The live `knowledge/index.md` in `okf-wealth-base` is explicit about that contract. It says to read the index first, select the scenario, open only the linked concept files, and read holding calculation before redemption optimization when building an end-to-end redemption workflow.

That maps cleanly to the OKF spec. The bundle is the repository. The index is the directory listing. The concept documents are the markdown files that carry the actual knowledge:

`holding_calculation.md` has frontmatter type `logic_doc`. Its business meaning is holding derivation from BUY and SELL transactions.

`redemption_optimizer.md` has frontmatter type `strategy_doc`. Its business meaning is redemption lot selection using FIFO, exit-load checks, and partial-redemption rules.

The benefit is not only neat organization. It changes how the agent behaves.

- It gives the agent a small routing file first, instead of dumping every rule into the prompt.
- It lets the agent read only the concepts needed for the current task.
- It gives every business rule a reviewable file with frontmatter, title, description, and tags.
- It makes the final answer auditable because the agent can cite the exact concept documents it used.
- It lets domain experts maintain wealth logic without editing Python code or model prompts.

That structure solved a real problem. A single prompt can ask for transactions, holdings, and redemption optimization at once. The agent must not stop at the index. It must route into the right rules.

For the final redemption question, output validation confirmed the agent had read all three documents:

```text
2026-07-27 01:20:08,496 INFO okf_agent.agent validating OKF answer consulted_tool_urls=[
  'https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/holding_calculation.md',
  'https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/index.md',
  'https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/redemption_optimizer.md'
] output_instruction_urls=[
  'https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/holding_calculation.md',
  'https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/index.md',
  'https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/redemption_optimizer.md'
]
```

That validation line is the difference between “the prompt told it to read the rule” and “the system verified that it did.”

---

## Domain Model: Customers, Funds, Transactions, Holdings, and Redemption Lots

The domain was intentionally small:

- customers
- funds
- transactions
- current holdings
- redemption lots

The request log shows the important fields returned for customer `2`:

- Transaction `107`: fund `504`, Balanced Advantage Fund, `125` units, transaction date `2025-11-15`, exit-load period `180`, exit-load rate `1.00`, NAV `28.4000`.
- Transaction `103`: fund `502`, Short Duration Debt Fund, `50` units, transaction date `2026-02-01`, exit-load period `365`, exit-load rate `0.50`, NAV `12.2000`.
- Transaction `106`: fund `502`, Short Duration Debt Fund, `30` units, transaction date `2026-04-05`, exit-load period `365`, exit-load rate `0.50`, NAV `12.2000`.

That is enough to compute holdings and make a redemption recommendation.

For current holdings, the rule was simple: sum buys and subtract sells. In this captured run, customer `2` had only buy rows.

The agent derived:

Fund `502`, Short Duration Debt Fund, had `80` units at NAV `12.20`, for value `976.00`.

Fund `504`, Balanced Advantage Fund, had `125` units at NAV `28.40`, for value `3550.00`.

The total value was `4526.00`.

![](.MEDIUM_images/25e653c0.png)

Show customers, transactions, fund master, holdings, and redemption lots with fund_id as the join key.

---

## Encoding Wealth Data Contracts with Frictionless Data Packages

The data contract belongs outside the agent.

Frictionless Data gave the project a way to describe resources, fields, formats, and validation rules without hiding them in application code.

The Data Package idea is a good fit here because the system has multiple resources that make sense as one dataset. A transaction table alone is not enough. Fund metadata, NAV, exit-load fields, and customer identifiers all need to move together.

The implementation used a datapackage as the published interface. The agent did not connect directly to arbitrary tables. It accessed resources exposed through `okf_mcp`.

```json
{
  "name": "wealth-management-core",
  "title": "Wealth Management Core",
  "description": "PostgreSQL-backed Frictionless Data Package for portfolio holdings and redemption analysis.",
  "resources": [
    {
      "name": "fund_master",
      "type": "table",
      "scheme": "postgresql",
      "format": "sql",
      "dialect": {
        "sql": {
          "table": "fund_master",
          "orderBy": "fund_id"
        }
      }
    },
    {
      "name": "transactions_by_customer",
      "type": "table",
      "scheme": "postgresql",
      "format": "sql",
      "dialect": {
        "sql": {
          "table": "transactions",
          "orderBy": "customer_id, transaction_date, transaction_id"
        }
      }
    },
    {
      "name": "redemption_lots",
      "type": "table",
      "scheme": "postgresql",
      "format": "sql",
      "dialect": {
        "sql": {
          "table": "redemption_lots",
          "orderBy": "customer_id, transaction_date, fund_id"
        }
      }
    },
    {
      "name": "exit_load_free_redemption_lots",
      "type": "table",
      "scheme": "postgresql",
      "format": "sql",
      "dialect": {
        "sql": {
          "table": "redemption_lots",
          "where": "exit_load_free",
          "orderBy": "customer_name, transaction_date, fund_name"
        }
      }
    }
  ]
}
```

The contract itself lives in `https://github.com/commitbyrajat/okf-wealth-base/blob/main/datapackage.json`. That matters because the data contract and the knowledge contract can be reviewed together. If a domain expert changes a redemption rule to depend on a new field, the datapackage has to expose that field. If a data engineer renames or reshapes a resource, the markdown rule has to remain accurate.

This was one of the safer design decisions. Once the resources were described and validated, the API and MCP tools could stay generic.

---

## Designing the Datapackage for SQL-Backed Resources

The most important resource for the captured run was `transactions_by_customer`.

The final answer named it explicitly:

```json
{
  "name": "transactions_by_customer (via get_customer_transactions)",
  "source_type": "mcp_tool",
  "reason": "To fetch all transaction rows for customer 2, NAVs, exit-load metadata and transaction dates used for holdings and exit-load checks."
}
```

The trade-off was where to put joins and transformations.

It is tempting to create a database view for every agent-facing query. That works early and becomes painful later. Instead, the design kept the source SQL resources clean and used Frictionless transformation behavior in the execution layer.

The public datapackage contract lists the base resources and the use-case resources side by side. The base resources are `customers`, `fund_master`, and `transactions`. The use-case resources include `transactions_by_customer`, `current_holdings`, `redemption_lots`, `open_holdings`, and `exit_load_free_redemption_lots`.

The result was a clearer boundary:

PostgreSQL handled source data and basic relational storage.

The Frictionless datapackage handled the resource contract.

`okf_mcp` handled validation, extraction, transformation, API exposure, and MCP exposure.

The agent handled orchestration and structured response.

That kept business behavior visible without turning the database into the only place rules could live.

---

## Validating Data Quality with Frictionless Checklist and Table Checks

A redemption recommendation is only as good as the rows behind it.

The project used Frictionless validation before reads. The details live in code and tests, but the design intent was straightforward:

- validate package metadata
- validate resources
- check table dimensions
- normalize errors into readable runtime messages

```text
test_empty_resource_fails_table_dimensions_check ... ok
test_valid_package_passes_metadata_and_resource_checks ... ok

----------------------------------------------------------------------
Ran 2 tests in 0.059s

OK
```

The failure path is also readable. An empty resource is converted into a
domain-facing runtime error instead of leaking a raw library exception:

```text
Package resource validation failed:
[customers] [table-dimensions] The data source does not have the required
dimensions: number of rows is 0, the minimum is 1
```

I did not want the agent discovering basic data-shape problems halfway through an answer.

This is one of those non-glamorous pieces that matters more than it looks. A missing fund id or malformed NAV would make the final recommendation worse than useless. It would make it confidently wrong.

---

## Transforming Data Without Database-Specific Business Views

There was a design decision around transformation.

Should the project create new SQL views for agent-specific answers, or should it keep the database generic and use Frictionless transformations?

The final design favored Frictionless transformations. The reason was practical. The agent needed data shaped for a use case, but the underlying contract should not become a pile of custom views for each question.

For the captured run, the agent got transaction rows that already included fund details needed for the answer:

- fund name
- AMC name
- NAV
- NAV date
- exit-load period
- exit-load rate

That made the MCP tool useful without forcing the model to invent joins.

```python
def extract_transactions_by_customer(
    package: Package,
    customer_id: int,
) -> list[Row]:
    descriptor = package.get_resource(TRANSACTIONS_BY_CUSTOMER_RESOURCE).to_descriptor()
    descriptor["name"] = TRANSACTIONS_BY_CUSTOMER_RESOURCE
    descriptor.setdefault("dialect", {}).setdefault("sql", {})
    descriptor["dialect"]["sql"]["where"] = f"customer_id = {customer_id}"

    filtered_resource = Resource.from_descriptor(descriptor)
    transaction_rows = filtered_resource.extract()[TRANSACTIONS_BY_CUSTOMER_RESOURCE]
    fund_rows = extract_rows(package, FUND_MASTER_RESOURCE)
    return join_transactions_with_fund_details(transaction_rows, fund_rows)


def join_transactions_with_fund_details(
    transaction_rows: list[Row],
    fund_rows: list[Row],
) -> list[Row]:
    package = Package(
        resources=[
            rows_to_table_resource(
                TRANSACTIONS_BY_CUSTOMER_RESOURCE,
                transaction_rows,
                ["transaction_id", "customer_id", "fund_id", "type", "units"],
            ),
            rows_to_table_resource(
                FUND_MASTER_RESOURCE,
                fund_rows,
                ["fund_id", "fund_name", "exit_load_period_days", "current_nav"],
            ),
        ]
    )
    transformed = transform(
        package,
        steps=[
            steps.resource_transform(
                name=TRANSACTIONS_BY_CUSTOMER_RESOURCE,
                steps=[
                    steps.table_normalize(),
                    steps.table_join(resource=FUND_MASTER_RESOURCE, field_name="fund_id"),
                    steps.row_sort(field_names=["customer_id", "transaction_id"]),
                ],
            )
        ],
    )
    return transformed.get_resource(TRANSACTIONS_BY_CUSTOMER_RESOURCE).read_rows()
```

The trade-off is that the execution layer becomes more important. That is acceptable if it is tested and observable.

---

## 11. Exposing OKF Resources through FastAPI and FastMCP

The system exposed two interfaces.

FastAPI handled direct HTTP checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/resources
curl "http://127.0.0.1:8000/customers/2/transactions"
curl "http://127.0.0.1:8000/instructions?include_linked=false"
```

FastMCP handled agent tool access:

```text
http://127.0.0.1:8000/mcp/
```

The run log showed MCP session negotiation at the start:

```text
2026-07-27 01:18:54,074 INFO httpx HTTP Request: POST http://127.0.0.1:8000/mcp/ "HTTP/1.1 200 OK"
2026-07-27 01:18:54,074 INFO mcp.client.streamable_http Received session ID: d368b8b8637e413d8362397b4ec54ef1
2026-07-27 01:18:54,074 INFO mcp.client.streamable_http Negotiated protocol version: 2025-11-25
```

That log line helped later. When the agent misbehaved, I could separate MCP connectivity from model behavior.

![](.MEDIUM_images/2dececac.png)

---

## Reading OKF Markdown Instructions as Runtime Knowledge

The `/instructions` endpoint became a small but important bridge.

It reads a markdown URL, normalizes GitHub blob URLs to raw URLs, extracts markdown links, and returns the content plus next-document links.

The index read returned two links:

```text
2026-07-27 01:19:04,818 INFO okf_agent.agent read OKF instructions resolved_url=https://raw.githubusercontent.com/commitbyrajat/okf-wealth-base/main/knowledge/index.md links=2
```

For the redemption optimizer question, those links led to:

- `holding_calculation.md`
- `redemption_optimizer.md`

The agent system prompt alone was not enough. The output validator also checked that the final answer cited only instruction URLs that were actually read.

That was a useful guardrail. It caught the difference between a plausible answer and a traceable answer.

---

## Agent Architecture with Pydantic AI

The agent had four main responsibilities:

1. Read the OKF index.
2. Read scenario documents selected from the index.
3. Call MCP tools for data.
4. Return a structured answer.

The captured redemption run shows that sequence:

At `01:18:54`, the agent run started, the memory pool opened, and the MCP session was negotiated.

At `01:19:04`, the index document was read.

At `01:19:10`, the holding calculation document was read.

At `01:19:20`, the redemption optimizer document was read.

At `01:19:26`, the MCP data call happened.

At `01:20:08`, output validation ran and the interaction memory record was written.

The whole captured redemption run took about 74 seconds from `01:18:54` to `01:20:08`.

That is not a performance benchmark. It is just the observed timing from the run log. The important part is the shape: tool work, rule reads, data read, validation, cleanup.

```python
def build_agent(
    settings: AgentSettings | None = None,
    *,
    memory: Memory[OkfAgentDeps] | None = None,
) -> Agent[OkfAgentDeps, OkfAgentAnswer]:
    resolved_settings = settings or AgentSettings()
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
        toolsets=[MCPToolset(resolved_settings.mcp_url, include_instructions=True)],
        capabilities=[memory] if memory is not None else [],
        defer_model_check=True,
        retries={"output": 1},
    )

    @agent.tool
    async def read_okf_instructions(
        ctx: RunContext[OkfAgentDeps],
        url: str = DEFAULT_INSTRUCTIONS_URL,
        include_linked: bool = False,
        max_depth: int = 1,
    ) -> InstructionDocument:
        response = await ctx.deps.http_client.get(
            "/instructions",
            params={
                "url": url,
                "include_linked": include_linked,
                "max_depth": max_depth,
            },
        )
        response.raise_for_status()

        document = InstructionDocument.model_validate(response.json())
        ctx.deps.consulted_instruction_urls.add(document.resolved_url)
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

        if normalize_instruction_url(DEFAULT_INSTRUCTIONS_URL) not in consulted_urls:
            raise ModelRetry(
                "Read the OKF knowledge index before returning the final answer."
            )

        missing_reads = output_urls - consulted_urls
        if missing_reads:
            raise ModelRetry(
                "Only cite instruction URLs actually read with read_okf_instructions. "
                f"These URLs were cited but not read: {sorted(missing_reads)}"
            )
        return output

    return agent
```

---

## Enforcing Structured Answers with Pydantic Output Models

The final answer was not plain text.

It contained:

- `scenario`
- `answer`
- `instruction_urls`
- `consulted_instructions`
- `data_sources`
- `assumptions`

For the redemption run, the scenario was:

```json
{
  "scenario": "redemption_optimization"
}
```

The consulted instruction list included:

```json
[
  {
    "title": "Wealth Management Knowledge Directory",
    "role": "index"
  },
  {
    "title": "Customer Holding Calculation",
    "role": "scenario_rule"
  },
  {
    "title": "Redemption Optimization",
    "role": "scenario_rule"
  }
]
```

The schema forced the answer to carry its provenance.

That mattered during debugging. If the agent skipped `redemption_optimizer.md`, the final output would not satisfy the validator for a redemption scenario.

---

## Long-Term Agent Memory with Pydantic AI Harness and PostgreSQL

Memory caused more confusion than I expected.

At first, I expected rows to appear just because the agent ran. That was the wrong assumption. Pydantic AI Harness memory is not a chat transcript by default. It gives the agent memory tools, and rows appear when memory is written.

So I added app-level interaction memory. Every run writes an `INTERACTIONS.md` record before the model call. Explicit “remember ...” prompts write to `MEMORY.md`.

The run log showed the interaction write:

```text
2026-07-27 01:18:54,068 INFO okf_agent.agent persisted interaction start path=default/okf_agent/INTERACTIONS.md
...
2026-07-27 01:20:08,510 INFO okf_agent.agent persisted interaction result path=default/okf_agent/INTERACTIONS.md
```

The database verification showed operation receipts:

```text
id                                                     | version | existed | completed
-------------------------------------------------------+---------+---------+-----------
okf_agent:app_append:2c8b6f28c341e4e3a94aa2446322cd08 | 4       | t       | t
okf_agent:app_append:3420c6674d4f2aaf2a102dc30e569002 | 3       | f       | t
okf_agent:app_append:3439c30c5c0456af0ef606c4c9ab5e63 | 6       | t       | t
okf_agent:app_append:3dfe40bb71c12fb4697424378266eb79 | 5       | t       | t
okf_agent:app_append:b346ee1e0142871e6dfdc97e2b1c1bb0 | 7       | t       | t
```

That second table, `agent_memory_operations`, became important. It told me the writes were going through harness-style operation receipts, not just force-populating content rows.

![](.MEDIUM_images/bb6c56dc.png)

---

## Redemption Optimizer Flow: From User Question to Recommendation

The full redemption question was:

```bash
uv run okf-agent "Show transactions for customer 2 and list the holdings and optimize redemptions" --json | jq
```

The final recommendation came from three inputs:

Customer transactions came from `transactions_by_customer` through MCP.

Holding rules came from `holding_calculation.md`.

Redemption rules came from `redemption_optimizer.md`.

The answer followed a clean path:

1. Fetch customer `2` transactions.
2. Group units by fund.
3. Compute current value from NAV.
4. Compare holding period against exit-load period.
5. Prefer exit-load-free units.
6. Apply FIFO within the lots.

The output captured the practical advice:

```text
Prefer redeeming from lots with no exit load first. That makes the Balanced
Advantage Fund (fund 504, 125 units) the top candidate because its holding
period (253 days) exceeds the 180-day exit-load window.
```

And then:

```text
Only if a redemption request exceeds 125 units (or the cash needed exceeds
~3550.00) should you consider Short Duration Debt Fund (fund 502) lots.
Both 502 lots are within the 365-day exit-load window.
```

That answer is not a replacement for an execution system. It is a decision aid. It gives the user the next question: how many units or how much value do you want to redeem?

---

## Observability: Logs for Instruction Reads, MCP Calls, and Memory Writes

The system became easier to trust once the logs described the actual path.

For one run, I could see:

- model calls to OpenAI
- instruction reads through `/instructions`
- MCP session negotiation
- MCP calls
- output validation
- memory start/result writes
- MCP cleanup
- memory pool close

The cleanup mattered too:

```text
2026-07-27 01:20:08,502 INFO httpx HTTP Request: DELETE http://127.0.0.1:8000/mcp/ "HTTP/1.1 200 OK"
2026-07-27 01:20:08,510 INFO okf_agent.agent persisted interaction result path=default/okf_agent/INTERACTIONS.md
2026-07-27 01:20:08,510 INFO okf_agent.agent completed OKF agent run session_id=default instruction_count=3
2026-07-27 01:20:08,514 INFO okf_agent.agent closed OKF agent memory pool
```

Without those lines, debugging would have been guesswork.

With them, I could answer simple questions:

- Did the agent read the index?
- Did it read the scenario rule?
- Did MCP connect?
- Did the answer pass provenance validation?
- Did memory persist?

---

## Captured Logs from the Implementation Runbook

The runbook has two useful successful runs.

The first was a complete redemption optimizer run. It read the index, holding rules, redemption rules, called MCP, validated output, and wrote memory.

The second was a simpler customer transaction run. It read the index and holding calculation document, then returned the three transactions for customer `2`.

The holding-only run completed in about 62 seconds, from `01:06:03` to `01:07:05`.

The full redemption run completed in about 74 seconds, from `01:18:54` to `01:20:08`.

The customer transactions run used instruction count `2`, scenario `customer_transactions`, and evidence from the index plus holding calculation.

The redemption optimizer run used instruction count `3`, scenario `redemption_optimization`, and evidence from the index, holding calculation, and redemption optimizer.

The memory table also captured the result summary:

```text
default/okf_agent/INTERACTIONS.md
- user_prompt: Show transactions for customer 2
- scenario: customer_transactions
- instruction_urls: https://raw.githubusercontent.com/.../index.md, https://raw.githubusercontent.com/.../holding_calculation.md
- answer_summary: Transactions for customer 2 (3 rows): ...
```

For the redemption run, the interaction record included:

```text
- scenario: redemption_optimization
- instruction_urls: https://raw.githubusercontent.com/.../index.md,
  https://raw.githubusercontent.com/.../holding_calculation.md,
  https://raw.githubusercontent.com/.../redemption_optimizer.md
```

This is the kind of logging I want in agent systems. Not verbose for the sake of it. Just enough to reconstruct the reasoning path.

---

## Failure Modes: Token Limits, Provider Timeouts, Empty Memory Tables, and Data Drift

The operational risks fell into a few buckets.

Provider delay showed up as OpenAI response calls dominating run time. The guardrail was a model request timeout plus a full run timeout.

A missing instruction read showed up when the agent stopped after the index. The guardrail was an output validator that requires scenario documents.

An empty memory table showed up after the wrong assumption that normal agent execution would always create memory rows. The fix was an app-level `INTERACTIONS.md` write before the model call.

An empty operation table meant content had been written without an operation receipt. The fix was to pass writes through `MemoryOperation`.

A large final answer needed more output room. The output-token setting moved into environment configuration.

I had to correct my own assumption about memory. The harness was configured, but that did not mean every run automatically created a useful row. Once the app wrote an interaction record at run start, memory verification became deterministic.

The token limit was another practical lesson. A structured JSON answer that includes transactions, holdings, recommendations, citations, data sources, and assumptions needs room. The captured runbook records the timeout boundaries, not the full token-limit stack trace. The operational fix was still clear: keep the output-token budget in `.env` with the rest of the runtime configuration.

```text
OKF_AGENT_MODEL=openai:gpt-5-mini
OKF_MCP_URL=http://127.0.0.1:8000/mcp/
OKF_API_BASE_URL=http://127.0.0.1:8000
OKF_AGENT_MEMORY_DSN=postgresql://okf_agent:okf_agent_password@127.0.0.1:5433/okf_agent_memory

OKF_AGENT_REQUEST_TIMEOUT_SECONDS=20
OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS=60
OKF_AGENT_RUN_TIMEOUT_SECONDS=180
OKF_AGENT_MAX_MODEL_REQUESTS=8
OKF_AGENT_MAX_TOOL_CALLS=16
OKF_AGENT_MAX_OUTPUT_TOKENS=4000
OKF_AGENT_LOG_LEVEL=INFO
```

The agent also logs its timeout settings at startup:

```text
run_timeout_seconds=180.0 model_timeout_seconds=60.0
```

That line is small, but it saves time during incidents.

---

## Testing Strategy for Data, API, MCP, Agent, and Memory Behavior

The tests were not trying to prove that an LLM is always correct.

They focused on the boundaries:

- datapackage loading
- Frictionless validation
- resource extraction
- customer transaction filtering
- instruction URL normalization
- markdown link extraction
- FastAPI routes
- MCP tool descriptions and calls
- Pydantic output schema
- memory write behavior

```bash
cd okf_wealth_ai/okf_agent
uv run coverage run -m unittest discover
uv run coverage report -m
```

The agent package now uses `coverage.py` through `coverage[toml]`. The measured run passed 19 tests:

```text
Ran 19 tests in 0.011s

OK
```

The coverage report for `src/okf_agent` was:

`src/okf_agent/__init__.py` had 4 statements, 0 missing statements, 0 branches, 0 partial branches, and 100% coverage.

`src/okf_agent/agent.py` had 160 statements, 60 missing statements, 24 branches, 6 partial branches, and 59% coverage.

`src/okf_agent/cli.py` had 35 statements, 35 missing statements, 8 branches, 0 partial branches, and 0% coverage.

`src/okf_agent/config.py` had 25 statements, 0 missing statements, 0 branches, 0 partial branches, and 100% coverage.

`src/okf_agent/logging_config.py` had 5 statements, 2 missing statements, 0 branches, 0 partial branches, and 60% coverage.

`src/okf_agent/models.py` had 47 statements, 1 missing statement, 4 branches, 1 partial branch, and 96% coverage.

`src/okf_agent/test_runner.py` had 6 statements, 6 missing statements, 0 branches, 0 partial branches, and 0% coverage.

Overall, the agent package had 282 statements, 104 missing statements, 36 branches, 7 partial branches, and 59% coverage.

That number is honest. The deterministic parts are well covered: settings, output models, instruction URL normalization, memory note extraction, app-level memory writes, and operation receipts. The weak spots are also clear. The CLI has no tests yet, and the live orchestration paths in `agent.py` still need integration tests around `/instructions`, MCP calls, timeout handling, and provider-error behavior.

The important design choice was where tests lived: around deterministic code, not around model prose.

That gave the agent freedom to phrase the answer while keeping the system behavior constrained.

---

## What This Architecture Gets Right

The best part of the design is the separation of contracts.

Data shape is governed by the Frictionless datapackage.

Business rules are governed by OKF-style markdown.

Tool access is governed by FastMCP.

HTTP debugging is handled through FastAPI.

Agent output is governed by the Pydantic model.

Memory persistence is handled by Pydantic AI Harness and PostgreSQL.

Domain ownership is handled through `okf-wealth-base` pull requests reviewed by wealth, risk, operations, compliance, and engineering.

The agent is not trusted blindly. It has to read instructions. It has to use tools. It has to return structured data. It has to pass validation.

The captured logs prove the path:

```text
read OKF instructions ... index.md links=2
read OKF instructions ... holding_calculation.md links=0
read OKF instructions ... redemption_optimizer.md links=0
validating OKF answer consulted_tool_urls=[...] output_instruction_urls=[...]
```

That is a stronger posture than “the prompt says it should.”

For a retail bank, this is also an accountability posture. The recommendation logic cannot live only in a model prompt owned by a platform team. It has to be inspectable by the people who are responsible for the advice, the product, the operational process, and the regulatory language. Git is not perfect governance, but it gives the organization a review trail that plain chatbot configuration does not.

---

## What I Would Improve Next

I would make the redemption amount explicit.

The current captured run gives a recommendation and examples. It does not execute a lot-level redemption plan for a specific amount because the prompt did not provide an amount. The agent correctly asked for the next input:

> How many units or what redemption amount would you like to execute?

The next version should accept an amount and return exact sell instructions:

- fund id
- transaction lot
- units to redeem
- estimated gross value
- exit-load amount
- estimated net proceeds

I would also keep reducing model work.

The agent currently makes multiple provider calls during a run. The logs show that model calls are the slowest part of the path. More deterministic pre-processing in the MCP layer would reduce cost and latency.

The final improvement is better article-quality observability: a short trace id that connects the CLI run, MCP session, API calls, and memory writes.

---

## Conclusion: OKF as an Executable Knowledge Contract

The main shift was mental.

I stopped treating markdown as documentation that humans may or may not read. I started treating it as a knowledge contract the system must read before answering.

Frictionless Data handled the dataset contract. OKF-style markdown handled the business rule contract. FastMCP made the data executable for the agent. Pydantic AI made the answer structured. Pydantic AI Harness made memory durable and inspectable.

The important organizational move was separating `okf-wealth-base` from the agent code. The knowledge base and `datapackage.json` should be maintained as bank-owned domain assets. Engineers can build the runtime, but domain experts should be able to approve the rules the runtime follows.

The final redemption optimizer answer was not magic. It was the result of a visible chain:

![](.MEDIUM_images/9f035f2d.png)

That chain is what made the answer worth trusting.

Not because an agent said it.

Because the system could show how it got there.
