from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from okf_exec.serializers import mask_url_password, to_jsonable


class SerializerTest(unittest.TestCase):
    def test_to_jsonable_converts_decimal_and_dates(self) -> None:
        value = {"amount": Decimal("12.34"), "day": date(2026, 1, 10)}

        self.assertEqual(
            to_jsonable(value),
            {"amount": "12.34", "day": "2026-01-10"},
        )

    def test_mask_url_password_hides_password_only(self) -> None:
        self.assertEqual(
            mask_url_password("postgresql://okf:secret@localhost:5432/okf_wealth"),
            "postgresql://okf:***@localhost:5432/okf_wealth",
        )
        self.assertEqual(mask_url_password("data/table.csv"), "data/table.csv")


if __name__ == "__main__":
    unittest.main()
