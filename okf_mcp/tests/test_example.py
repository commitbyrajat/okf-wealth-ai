from __future__ import annotations

import argparse
import unittest

from okf_exec.example import parse_customer_id


class ExampleCliTest(unittest.TestCase):
    def test_parse_customer_id_accepts_positive_integer(self) -> None:
        self.assertEqual(parse_customer_id("1"), 1)

    def test_parse_customer_id_allows_missing_value(self) -> None:
        self.assertIsNone(parse_customer_id(None))
        self.assertIsNone(parse_customer_id(""))

    def test_parse_customer_id_rejects_invalid_values(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_customer_id("abc")

        with self.assertRaises(argparse.ArgumentTypeError):
            parse_customer_id("0")


if __name__ == "__main__":
    unittest.main()
