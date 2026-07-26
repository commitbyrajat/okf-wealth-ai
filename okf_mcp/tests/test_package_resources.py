from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from frictionless import Package
from frictionless.resources import TableResource

from okf_exec.package_resources import (
    extract_rows,
    extract_transactions_by_customer,
    has_resources,
    join_transactions_with_fund_details,
    resource_names,
)


class PackageResourcesTest(unittest.TestCase):
    def test_resource_names_and_presence_checks(self) -> None:
        package = Package(
            resources=[
                TableResource(name="transactions", data=[["id"], [1]]),
                TableResource(name="fund_master", data=[["id"], [501]]),
            ]
        )

        self.assertEqual(resource_names(package), {"transactions", "fund_master"})
        self.assertTrue(has_resources(package, "transactions", "fund_master"))
        self.assertFalse(has_resources(package, "customers"))

    def test_extract_rows_returns_named_resource_rows(self) -> None:
        package = Package(
            resources=[
                TableResource(name="transactions", data=[["id", "type"], [1, "BUY"]])
            ]
        )

        self.assertEqual(
            extract_rows(package, "transactions"), [{"id": 1, "type": "BUY"}]
        )

    def test_extract_transactions_by_customer_applies_sql_where_filter(self) -> None:
        source_resource = Mock()
        source_resource.to_descriptor.return_value = {
            "name": "transactions_by_customer",
            "path": "postgresql://example",
            "dialect": {"sql": {"table": "transactions"}},
        }
        package = Mock()
        package.resources = [Mock()]
        package.resources[0].name = "transactions_by_customer"
        package.get_resource.return_value = source_resource

        filtered_resource = Mock()
        filtered_resource.extract.return_value = {
            "transactions_by_customer": [{"transaction_id": 101, "customer_id": 1}]
        }

        with patch(
            "okf_exec.package_resources.Resource.from_descriptor",
            return_value=filtered_resource,
        ) as from_descriptor, patch(
            "okf_exec.package_resources.extract_rows",
            return_value=[{"fund_id": 501, "fund_name": "Bluechip Equity Fund"}],
        ), patch(
            "okf_exec.package_resources.join_transactions_with_fund_details",
            return_value=[{"transaction_id": 101, "customer_id": 1}],
        ) as join:
            rows = extract_transactions_by_customer(package, 1)

        descriptor = from_descriptor.call_args.args[0]
        self.assertEqual(descriptor["dialect"]["sql"]["where"], "customer_id = 1")
        join.assert_called_once()
        self.assertEqual(rows, [{"transaction_id": 101, "customer_id": 1}])

    def test_extract_transactions_by_customer_falls_back_to_transactions(self) -> None:
        source_resource = Mock()
        source_resource.to_descriptor.return_value = {
            "name": "transactions",
            "path": "postgresql://example",
            "dialect": {"sql": {"table": "transactions"}},
            "schema": {
                "fields": [],
                "foreignKeys": [
                    {"fields": "customer_id", "reference": {"resource": "customers"}}
                ],
            },
        }
        package = Mock()
        package.resources = [Mock(name="transactions")]
        package.resources[0].name = "transactions"
        package.get_resource.return_value = source_resource

        filtered_resource = Mock()
        filtered_resource.extract.return_value = {
            "transactions_by_customer": [{"transaction_id": 101, "customer_id": 1}]
        }

        with patch(
            "okf_exec.package_resources.Resource.from_descriptor",
            return_value=filtered_resource,
        ) as from_descriptor, patch(
            "okf_exec.package_resources.extract_rows",
            return_value=[{"fund_id": 501, "fund_name": "Bluechip Equity Fund"}],
        ), patch(
            "okf_exec.package_resources.join_transactions_with_fund_details",
            return_value=[{"transaction_id": 101, "customer_id": 1}],
        ):
            rows = extract_transactions_by_customer(package, 1)

        package.get_resource.assert_called_once_with("transactions")
        descriptor = from_descriptor.call_args.args[0]
        self.assertEqual(descriptor["name"], "transactions_by_customer")
        self.assertNotIn("foreignKeys", descriptor["schema"])
        self.assertEqual(descriptor["dialect"]["sql"]["where"], "customer_id = 1")
        self.assertEqual(rows, [{"transaction_id": 101, "customer_id": 1}])

    def test_extract_transactions_by_customer_rejects_non_positive_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integer"):
            extract_transactions_by_customer(Mock(), 0)

    def test_join_transactions_with_fund_details_uses_frictionless_table_join(
        self,
    ) -> None:
        rows = join_transactions_with_fund_details(
            [
                {
                    "transaction_id": 101,
                    "customer_id": 1,
                    "fund_id": 501,
                    "type": "BUY",
                    "units": 100,
                    "transaction_date": "2026-01-10",
                }
            ],
            [
                {
                    "fund_id": 501,
                    "fund_name": "Bluechip Equity Fund",
                    "amc_name": "Northstar AMC",
                    "category": "Large Cap Equity",
                    "exit_load_period_days": 90,
                    "exit_load_rate": 1,
                    "current_nav": 45.5,
                    "nav_date": "2026-07-25",
                }
            ],
        )

        self.assertEqual(rows[0]["fund_name"], "Bluechip Equity Fund")
        self.assertEqual(rows[0]["amc_name"], "Northstar AMC")
        self.assertEqual(rows[0]["category"], "Large Cap Equity")


if __name__ == "__main__":
    unittest.main()
