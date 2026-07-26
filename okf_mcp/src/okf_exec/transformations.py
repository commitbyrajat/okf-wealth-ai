from __future__ import annotations

from decimal import Decimal
from typing import Any

from frictionless import steps, transform
from frictionless.exception import FrictionlessException
from frictionless.resources import TableResource

from .errors import format_frictionless_exception
from .package_resources import Row


def format_money(value: Decimal) -> str:
    return f"{value:,.2f}"


def format_units(value: Decimal) -> str:
    return f"{value:,.4f}"


class RowTransformer:
    def transform(
        self,
        rows: list[Row],
        field_names: list[str],
        transform_steps: list[Any],
        *,
        name: str,
    ) -> list[Row]:
        resource = self._to_resource(rows, field_names, name=name)
        try:
            transformed = transform(resource, steps=transform_steps)
            return transformed.read_rows()
        except FrictionlessException as exception:
            message = format_frictionless_exception(exception)
            raise RuntimeError(
                f"Resource transform failed for {name}:\n{message}"
            ) from exception

    def _to_resource(
        self,
        rows: list[Row],
        field_names: list[str],
        *,
        name: str,
    ) -> TableResource:
        data: list[list[Any]] = [field_names]
        data.extend([[row[field_name] for field_name in field_names] for row in rows])
        return TableResource(name=name, data=data)


def open_holdings_steps() -> list[Any]:
    return [
        steps.table_normalize(),
        steps.row_sort(field_names=["customer_name", "fund_name"]),
        steps.field_filter(
            names=[
                "customer_name",
                "fund_name",
                "units",
                "current_nav",
                "market_value",
            ]
        ),
        steps.field_update(name="units", descriptor={"type": "string"}),
        steps.field_update(name="market_value", descriptor={"type": "string"}),
        steps.cell_convert(field_name="units", function=format_units),
        steps.cell_convert(field_name="market_value", function=format_money),
    ]


def exit_load_free_lots_steps() -> list[Any]:
    return [
        steps.table_normalize(),
        steps.row_sort(field_names=["customer_name", "transaction_date", "fund_name"]),
        steps.row_slice(head=10),
        steps.field_filter(
            names=[
                "customer_name",
                "fund_name",
                "units",
                "transaction_date",
                "holding_period_days",
            ]
        ),
        steps.field_update(name="units", descriptor={"type": "string"}),
        steps.cell_convert(field_name="units", function=format_units),
    ]
