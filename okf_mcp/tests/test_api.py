from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from okf_exec.api import create_app


class FakeResourceService:
    def list_resources(self):
        return [{"name": "transactions", "fields": ["transaction_id"]}]

    def get_resource_schema(self, resource_name: str):
        if resource_name == "missing":
            raise ValueError('unknown resource "missing"')
        return {"name": resource_name, "schema": {"fields": []}}

    def read_resource_rows(self, resource_name: str, *, limit_rows: int = 100):
        return {
            "resource": resource_name,
            "count": 1,
            "rows": [{"transaction_id": 101}],
        }

    def get_customer_transactions(self, customer_id: int):
        return {
            "resource": "transactions_by_customer",
            "customer_id": customer_id,
            "count": 1,
            "rows": [{"transaction_id": 101, "customer_id": customer_id}],
        }


class FakeInstructionReader:
    def read(
        self,
        url: str,
        *,
        include_linked: bool = False,
        max_depth: int = 1,
    ):
        if url == "https://example.com/fail.md":
            raise RuntimeError("upstream read failed")
        return {
            "url": url,
            "resolved_url": "https://example.com/index.md",
            "content": "# Index\n\n[Funds](funds.md)",
            "links": [
                {
                    "title": "Funds",
                    "url": "funds.md",
                    "resolved_url": "https://example.com/funds.md",
                }
            ],
            "include_linked": include_linked,
            "max_depth": max_depth,
        }


class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            create_app(
                FakeResourceService(), instruction_reader=FakeInstructionReader()
            )
        )

    def test_health_check(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_root_redirects_to_docs(self) -> None:
        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/docs")

    def test_list_resources(self) -> None:
        response = self.client.get("/resources")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "transactions")

    def test_get_resource_schema_maps_missing_resource_to_404(self) -> None:
        response = self.client.get("/resources/missing/schema")

        self.assertEqual(response.status_code, 404)
        self.assertIn("unknown resource", response.json()["detail"])

    def test_read_resource_rows(self) -> None:
        response = self.client.get("/resources/transactions/rows?limit_rows=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rows"], [{"transaction_id": 101}])

    def test_get_customer_transactions(self) -> None:
        response = self.client.get("/customers/1/transactions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["customer_id"], 1)

    def test_read_instructions(self) -> None:
        response = self.client.get(
            "/instructions?url=https://example.com/index.md&include_linked=true&max_depth=2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "# Index\n\n[Funds](funds.md)")
        self.assertTrue(response.json()["include_linked"])
        self.assertEqual(response.json()["max_depth"], 2)

    def test_read_instructions_maps_upstream_failure_to_502(self) -> None:
        response = self.client.get("/instructions?url=https://example.com/fail.md")

        self.assertEqual(response.status_code, 502)
        self.assertIn("upstream read failed", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
