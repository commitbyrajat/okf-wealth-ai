from __future__ import annotations

from typing import Any

from frictionless import Checklist, Package, checks, validate
from frictionless.exception import FrictionlessException

from .errors import format_frictionless_exception, format_report_errors


class PackageValidator:
    def build_resource_checklist(self, resource: Any) -> Checklist:
        table_check_options: dict[str, int] = {"min_rows": 1}
        if resource.schema:
            table_check_options["num_fields"] = len(resource.schema.fields)
        return Checklist(checks=[checks.table_dimensions(**table_check_options)])

    def validate_metadata(self, package: Package) -> None:
        try:
            package.to_descriptor(validate=True)
        except FrictionlessException as exception:
            message = format_frictionless_exception(exception)
            raise RuntimeError(
                f"Package metadata validation failed:\n{message}"
            ) from exception

    def validate(self, package: Package) -> None:
        self.validate_metadata(package)
        failures: list[str] = []

        for resource in package.resources:
            resource_name = resource.name or str(resource.path or "resource")
            try:
                report = validate(
                    resource,
                    checklist=self.build_resource_checklist(resource),
                )
            except FrictionlessException as exception:
                message = format_frictionless_exception(exception)
                raise RuntimeError(
                    f"Resource validation failed for {resource_name}:\n{message}"
                ) from exception

            if not report.valid:
                failures.extend(
                    format_report_errors(report, resource_name=resource_name)
                )

        if failures:
            raise RuntimeError(
                "Package resource validation failed:\n" + "\n".join(failures)
            )
