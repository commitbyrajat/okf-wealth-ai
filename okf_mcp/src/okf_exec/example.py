from __future__ import annotations

import argparse

from frictionless import Package

from .package_loader import PackageLoader
from .package_resources import has_resources, resource_names
from .presentation import SummaryPresenter
from .settings import DEFAULT_PACKAGE_SOURCE

GITHUB_DATAPACKAGE_URL = DEFAULT_PACKAGE_SOURCE.datapackage_url
DATAPACKAGE_SOURCE_ENV = DEFAULT_PACKAGE_SOURCE.env_var


def _github_repository_url() -> str:
    return DEFAULT_PACKAGE_SOURCE.repository_url


def _resource_names(package: Package) -> set[str]:
    return resource_names(package)


def _has_resources(package: Package, *names: str) -> bool:
    return has_resources(package, *names)


def load_package_from_github() -> Package:
    return PackageLoader().load_from_github()


def load_valid_package() -> Package:
    return PackageLoader().load()


def print_sql_package_summary(package: Package) -> None:
    SummaryPresenter().print_sql_package_summary(package)


def print_csv_package_summary(package: Package) -> None:
    SummaryPresenter().print_csv_package_summary(package)


def parse_customer_id(value: str | None) -> int | None:
    if value in {None, ""}:
        return None
    try:
        customer_id = int(value)
    except ValueError as exception:
        raise argparse.ArgumentTypeError(
            "customer id must be an integer"
        ) from exception
    if customer_id <= 0:
        raise argparse.ArgumentTypeError("customer id must be a positive integer")
    return customer_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run OKF wealth management Frictionless examples."
    )
    parser.add_argument(
        "--customer-id",
        type=parse_customer_id,
        default=parse_customer_id(DEFAULT_PACKAGE_SOURCE.configured_customer_id),
        help=(
            "Filter the transactions_by_customer resource by customer id. "
            f"Can also be set with {DEFAULT_PACKAGE_SOURCE.customer_id_env_var}."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    package = load_valid_package()
    presenter = SummaryPresenter()

    if args.customer_id:
        presenter.print_customer_transactions(package, args.customer_id)
        return

    presenter.print(package)


if __name__ == "__main__":
    main()
