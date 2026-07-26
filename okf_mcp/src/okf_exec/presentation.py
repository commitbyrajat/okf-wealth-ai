from __future__ import annotations

import sys
from typing import TextIO

from frictionless import Package

from .package_resources import (
    extract_rows,
    extract_transactions_by_customer,
    has_resources,
    resource_names,
)
from .transformations import (
    RowTransformer,
    exit_load_free_lots_steps,
    open_holdings_steps,
)

OPEN_HOLDINGS_FIELDS = [
    "customer_name",
    "fund_name",
    "units",
    "current_nav",
    "market_value",
]
EXIT_LOAD_FREE_LOTS_FIELDS = [
    "customer_name",
    "fund_name",
    "units",
    "transaction_date",
    "holding_period_days",
]


class SummaryPresenter:
    def __init__(
        self,
        *,
        transformer: RowTransformer | None = None,
        output: TextIO = sys.stdout,
    ) -> None:
        self.transformer = transformer or RowTransformer()
        self.output = output

    def print(self, package: Package) -> None:
        if has_resources(package, "open_holdings", "exit_load_free_redemption_lots"):
            self.print_sql_package_summary(package)
            return

        if has_resources(package, "transactions", "fund_master"):
            self.print_csv_package_summary(package)
            return

        raise RuntimeError(
            f"Unsupported package resources: {sorted(resource_names(package))}"
        )

    def print_sql_package_summary(self, package: Package) -> None:
        holdings = self.transformer.transform(
            extract_rows(package, "open_holdings"),
            OPEN_HOLDINGS_FIELDS,
            open_holdings_steps(),
            name="open_holdings_summary",
        )
        exit_load_free_lots = self.transformer.transform(
            extract_rows(package, "exit_load_free_redemption_lots"),
            EXIT_LOAD_FREE_LOTS_FIELDS,
            exit_load_free_lots_steps(),
            name="exit_load_free_redemption_lots_summary",
        )

        print("Open holdings", file=self.output)
        for row in holdings:
            print(
                f"- {row['customer_name']}: {row['units']} units in "
                f"{row['fund_name']} at NAV {row['current_nav']} = "
                f"{row['market_value']}",
                file=self.output,
            )

        print("\nExit-load-free buy lots", file=self.output)
        for row in exit_load_free_lots:
            print(
                f"- {row['customer_name']}: {row['units']} units in "
                f"{row['fund_name']} bought on {row['transaction_date']} "
                f"({row['holding_period_days']} days)",
                file=self.output,
            )

    def print_csv_package_summary(self, package: Package) -> None:
        transactions = extract_rows(package, "transactions", limit_rows=10)
        funds = extract_rows(package, "fund_master", limit_rows=10)

        print("Transactions", file=self.output)
        for row in transactions:
            print(
                f"- #{row['transaction_id']}: customer {row['customer_id']} "
                f"{row['type']} {row['units']} units of fund {row['fund_id']} "
                f"on {row['transaction_date']}",
                file=self.output,
            )

        print("\nFunds", file=self.output)
        for row in funds:
            print(
                f"- {row['fund_id']}: NAV {row['current_nav']} "
                f"with {row['exit_load_period_days']} exit-load days",
                file=self.output,
            )

    def print_customer_transactions(self, package: Package, customer_id: int) -> None:
        transactions = extract_transactions_by_customer(package, customer_id)

        print(f"Transactions for customer {customer_id}", file=self.output)
        if not transactions:
            print("- No transactions found", file=self.output)
            return

        for row in transactions:
            fund_label = row.get("fund_name") or f"fund {row['fund_id']}"
            fund_detail = (
                f" ({row['category']}, {row['amc_name']})"
                if row.get("category") and row.get("amc_name")
                else ""
            )
            print(
                f"- #{row['transaction_id']}: {row['type']} {row['units']} units "
                f"of {fund_label}{fund_detail} on {row['transaction_date']}",
                file=self.output,
            )
