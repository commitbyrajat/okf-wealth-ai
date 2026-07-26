from __future__ import annotations

import unittest

from frictionless import Package
from frictionless.resources import TableResource

from okf_exec.validation import PackageValidator


class PackageValidatorTest(unittest.TestCase):
    def test_valid_package_passes_metadata_and_resource_checks(self) -> None:
        package = Package(
            resources=[
                TableResource(name="customers", data=[["id", "name"], [1, "Asha"]])
            ]
        )

        PackageValidator().validate(package)

    def test_empty_resource_fails_table_dimensions_check(self) -> None:
        package = Package(resources=[TableResource(name="customers", data=[["id"]])])

        with self.assertRaisesRegex(RuntimeError, "table-dimensions"):
            PackageValidator().validate(package)


if __name__ == "__main__":
    unittest.main()
