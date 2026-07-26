from __future__ import annotations

from typing import Any

from frictionless import Package, Resource, steps, transform
from frictionless.resources import TableResource

Row = dict[str, Any]
TRANSACTIONS_RESOURCE = "transactions"
TRANSACTIONS_BY_CUSTOMER_RESOURCE = "transactions_by_customer"
FUND_MASTER_RESOURCE = "fund_master"


def resource_names(package: Package) -> set[str]:
    return {resource.name for resource in package.resources if resource.name}


def has_resources(package: Package, *names: str) -> bool:
    available = resource_names(package)
    return all(name in available for name in names)


def extract_rows(
    package: Package,
    resource_name: str,
    *,
    limit_rows: int | None = None,
) -> list[Row]:
    extracted = package.extract(name=resource_name, limit_rows=limit_rows)
    return extracted[resource_name]


def extract_transactions_by_customer(
    package: Package,
    customer_id: int,
) -> list[Row]:
    if customer_id <= 0:
        raise ValueError("customer_id must be a positive integer")

    source_resource_name = (
        TRANSACTIONS_BY_CUSTOMER_RESOURCE
        if has_resources(package, TRANSACTIONS_BY_CUSTOMER_RESOURCE)
        else TRANSACTIONS_RESOURCE
    )
    resource = package.get_resource(source_resource_name)
    descriptor = resource.to_descriptor()
    descriptor["name"] = TRANSACTIONS_BY_CUSTOMER_RESOURCE
    if isinstance(descriptor.get("schema"), dict):
        descriptor["schema"].pop("foreignKeys", None)
    descriptor.setdefault("dialect", {}).setdefault("sql", {})
    descriptor["dialect"]["sql"]["where"] = f"customer_id = {customer_id}"

    filtered_resource = Resource.from_descriptor(descriptor)
    extracted = filtered_resource.extract()
    transaction_rows = extracted[TRANSACTIONS_BY_CUSTOMER_RESOURCE]
    fund_rows = extract_rows(package, FUND_MASTER_RESOURCE)
    return join_transactions_with_fund_details(transaction_rows, fund_rows)


def join_transactions_with_fund_details(
    transaction_rows: list[Row],
    fund_rows: list[Row],
) -> list[Row]:
    if not transaction_rows:
        return []

    package = Package(
        resources=[
            rows_to_table_resource(
                TRANSACTIONS_BY_CUSTOMER_RESOURCE,
                transaction_rows,
                [
                    "transaction_id",
                    "customer_id",
                    "fund_id",
                    "type",
                    "units",
                    "transaction_date",
                ],
            ),
            rows_to_table_resource(
                FUND_MASTER_RESOURCE,
                fund_rows,
                [
                    "fund_id",
                    "fund_name",
                    "amc_name",
                    "category",
                    "exit_load_period_days",
                    "exit_load_rate",
                    "current_nav",
                    "nav_date",
                ],
            ),
        ]
    )
    transformed = transform(
        package,
        steps=[
            steps.resource_transform(
                name=TRANSACTIONS_BY_CUSTOMER_RESOURCE,
                steps=[
                    steps.table_normalize(),
                    steps.table_join(
                        resource=FUND_MASTER_RESOURCE,
                        field_name="fund_id",
                    ),
                    steps.row_sort(
                        field_names=[
                            "customer_id",
                            "transaction_date",
                            "transaction_id",
                        ]
                    ),
                ],
            )
        ],
    )
    return transformed.get_resource(TRANSACTIONS_BY_CUSTOMER_RESOURCE).read_rows()


def rows_to_table_resource(
    name: str,
    rows: list[Row],
    field_names: list[str],
) -> TableResource:
    data = [field_names]
    data.extend([[row[field_name] for field_name in field_names] for row in rows])
    return TableResource(name=name, data=data)
