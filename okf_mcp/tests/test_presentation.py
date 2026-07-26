from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

from frictionless import Package
from frictionless.resources import TableResource

from okf_exec.presentation import SummaryPresenter


class SummaryPresenterTest(unittest.TestCase):
    def test_csv_package_summary_is_rendered_to_injected_output(self) -> None:
        output = StringIO()
        package = Package(
            resources=[
                TableResource(
                    name="transactions",
                    data=[
                        [
                            "transaction_id",
                            "customer_id",
                            "fund_id",
                            "type",
                            "units",
                            "transaction_date",
                        ],
                        [101, 1, 501, "BUY", 100, "2026-01-10"],
                    ],
                ),
                TableResource(
                    name="fund_master",
                    data=[
                        ["fund_id", "current_nav", "exit_load_period_days"],
                        [501, 45.5, 90],
                    ],
                ),
            ]
        )

        SummaryPresenter(output=output).print(package)

        rendered = output.getvalue()
        self.assertIn("Transactions", rendered)
        self.assertIn("#101", rendered)
        self.assertIn("Funds", rendered)
        self.assertIn("NAV 45.5", rendered)

    def test_customer_transactions_are_rendered_for_customer_id(self) -> None:
        output = StringIO()
        package = Package(resources=[TableResource(name="transactions_by_customer")])

        with patch(
            "okf_exec.presentation.extract_transactions_by_customer",
            return_value=[
                {
                    "transaction_id": 101,
                    "type": "BUY",
                    "units": 100,
                    "fund_id": 501,
                    "fund_name": "Bluechip Equity Fund",
                    "category": "Large Cap Equity",
                    "amc_name": "Northstar AMC",
                    "transaction_date": "2026-01-10",
                }
            ],
        ) as extract:
            SummaryPresenter(output=output).print_customer_transactions(package, 1)

        extract.assert_called_once_with(package, 1)
        rendered = output.getvalue()
        self.assertIn("Transactions for customer 1", rendered)
        self.assertIn("#101", rendered)
        self.assertIn("BUY 100 units", rendered)
        self.assertIn("Bluechip Equity Fund", rendered)
        self.assertIn("Large Cap Equity", rendered)


if __name__ == "__main__":
    unittest.main()
