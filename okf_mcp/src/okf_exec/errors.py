from __future__ import annotations

from typing import Any

from frictionless.exception import FrictionlessException


def format_error_descriptor(
    descriptor: dict[str, Any],
    *,
    resource_name: str | None = None,
) -> str:
    parts: list[str] = []
    if resource_name:
        parts.append(resource_name)

    error_type = descriptor.get("type")
    if error_type:
        parts.append(str(error_type))

    row = descriptor.get("rowPosition") or descriptor.get("rowNumber")
    field = descriptor.get("fieldName") or descriptor.get("fieldNumber")
    if row:
        parts.append(f"row={row}")
    if field:
        parts.append(f"field={field}")

    message = descriptor.get("message") or descriptor.get("note") or descriptor
    prefix = " ".join(f"[{part}]" for part in parts)
    return f"{prefix} {message}" if prefix else str(message)


def format_frictionless_exception(exception: FrictionlessException) -> str:
    return "\n".join(
        format_error_descriptor(error.to_descriptor())
        for error in exception.to_errors()
    )


def format_report_errors(report, *, resource_name: str | None = None) -> list[str]:
    errors: list[str] = []
    for error in report.errors:
        errors.append(
            format_error_descriptor(
                error.to_descriptor(),
                resource_name=resource_name,
            )
        )

    for task in report.tasks:
        task_name = resource_name or task.name
        for error in task.errors:
            errors.append(
                format_error_descriptor(
                    error.to_descriptor(),
                    resource_name=task_name,
                )
            )
    return errors
