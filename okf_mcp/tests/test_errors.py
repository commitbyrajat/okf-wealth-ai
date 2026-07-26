from __future__ import annotations

import unittest

from okf_exec.errors import format_error_descriptor


class ErrorFormattingTest(unittest.TestCase):
    def test_formats_type_location_and_message(self) -> None:
        message = format_error_descriptor(
            {
                "type": "field-count",
                "rowPosition": 3,
                "fieldName": "units",
                "message": "bad field count",
            },
            resource_name="transactions",
        )

        self.assertEqual(
            message,
            "[transactions] [field-count] [row=3] [field=units] bad field count",
        )

    def test_falls_back_to_note(self) -> None:
        message = format_error_descriptor({"type": "schema-error", "note": "bad"})

        self.assertEqual(message, "[schema-error] bad")


if __name__ == "__main__":
    unittest.main()
