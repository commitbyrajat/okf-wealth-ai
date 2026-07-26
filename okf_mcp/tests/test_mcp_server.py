from __future__ import annotations

import asyncio
import unittest

from fastmcp import Client

from okf_exec.mcp_server import create_mcp_server


class FakeResourceService:
    def list_resources(self):
        return [{"name": "transactions"}]

    def get_resource_schema(self, resource_name: str):
        return {"name": resource_name, "schema": {"fields": []}}

    def read_resource_rows(self, resource_name: str, *, limit_rows: int = 100):
        return {"resource": resource_name, "count": 0, "rows": []}

    def get_customer_transactions(self, customer_id: int):
        return {
            "resource": "transactions_by_customer",
            "customer_id": customer_id,
            "count": 0,
            "rows": [],
        }


class McpServerTest(unittest.TestCase):
    def test_all_tools_have_descriptions(self) -> None:
        async def run():
            async with Client(create_mcp_server(FakeResourceService())) as client:
                tools = await client.list_tools()
                return {tool.name: tool.description for tool in tools}

        descriptions = asyncio.run(run())

        self.assertEqual(
            set(descriptions),
            {
                "list_datapackage_resources",
                "get_resource_schema",
                "read_resource_rows",
                "get_customer_transactions",
            },
        )
        for description in descriptions.values():
            self.assertIsInstance(description, str)
            self.assertGreater(len(description), 20)

    def test_customer_transaction_tool_calls_service(self) -> None:
        async def run():
            async with Client(create_mcp_server(FakeResourceService())) as client:
                return await client.call_tool(
                    "get_customer_transactions",
                    {"customer_id": 1},
                )

        result = asyncio.run(run())

        self.assertEqual(result.data["customer_id"], 1)
        self.assertEqual(result.data["resource"], "transactions_by_customer")


if __name__ == "__main__":
    unittest.main()
