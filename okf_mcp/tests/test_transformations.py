from __future__ import annotations

import unittest
from decimal import Decimal

from okf_exec.transformations import (
    RowTransformer,
    exit_load_free_lots_steps,
    open_holdings_steps,
)


class RowTransformerTest(unittest.TestCase):
    def test_open_holdings_pipeline_sorts_filters_and_formats_display_rows(
        self,
    ) -> None:
        rows = [
            {
                "customer_name": "Zed",
                "fund_name": "Beta",
                "units": Decimal("2"),
                "current_nav": Decimal("10.0000"),
                "market_value": Decimal("20"),
                "ignored": "x",
            },
            {
                "customer_name": "Asha",
                "fund_name": "Alpha",
                "units": Decimal("1.5"),
                "current_nav": Decimal("40.0000"),
                "market_value": Decimal("60"),
                "ignored": "x",
            },
        ]

        transformed = RowTransformer().transform(
            rows,
            ["customer_name", "fund_name", "units", "current_nav", "market_value"],
            open_holdings_steps(),
            name="holdings",
        )

        self.assertEqual(transformed[0]["customer_name"], "Asha")
        self.assertEqual(transformed[0]["units"], "1.5000")
        self.assertEqual(transformed[0]["market_value"], "60.00")
        self.assertNotIn("ignored", transformed[0])

    def test_exit_load_pipeline_limits_to_ten_rows(self) -> None:
        rows = [
            {
                "customer_name": f"Customer {index:02d}",
                "fund_name": "Fund",
                "units": Decimal("1"),
                "transaction_date": "2026-01-01",
                "holding_period_days": index,
            }
            for index in range(12)
        ]

        transformed = RowTransformer().transform(
            rows,
            [
                "customer_name",
                "fund_name",
                "units",
                "transaction_date",
                "holding_period_days",
            ],
            exit_load_free_lots_steps(),
            name="lots",
        )

        self.assertEqual(len(transformed), 10)
        self.assertEqual(transformed[0]["units"], "1.0000")


if __name__ == "__main__":
    unittest.main()
