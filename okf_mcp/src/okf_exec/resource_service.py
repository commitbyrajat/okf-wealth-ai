from __future__ import annotations

from frictionless import Package

from .package_loader import PackageLoader
from .package_resources import (
    Row,
    extract_rows,
    extract_transactions_by_customer,
    resource_names,
)
from .serializers import mask_url_password, to_jsonable


class DatapackageResourceService:
    def __init__(self, *, loader: PackageLoader | None = None) -> None:
        self.loader = loader or PackageLoader()

    def list_resources(self) -> list[dict[str, object]]:
        package = self.loader.load()
        resources = []
        for resource in package.resources:
            descriptor = resource.to_descriptor()
            schema = descriptor.get("schema", {})
            fields = schema.get("fields", []) if isinstance(schema, dict) else []
            resources.append(
                {
                    "name": resource.name,
                    "type": descriptor.get("type"),
                    "scheme": descriptor.get("scheme"),
                    "format": descriptor.get("format"),
                    "path": mask_url_password(descriptor.get("path")),
                    "fields": [field.get("name") for field in fields],
                }
            )
        return to_jsonable(resources)

    def get_resource_schema(self, resource_name: str) -> dict[str, object]:
        package = self.loader.load()
        self._ensure_resource_exists(package, resource_name)
        resource = package.get_resource(resource_name)
        descriptor = resource.to_descriptor()
        return to_jsonable(
            {
                "name": resource.name,
                "schema": descriptor.get("schema", {}),
                "dialect": descriptor.get("dialect", {}),
                "path": mask_url_password(descriptor.get("path")),
            }
        )

    def read_resource_rows(
        self,
        resource_name: str,
        *,
        limit_rows: int | None = 100,
    ) -> dict[str, object]:
        self._validate_limit(limit_rows)
        package = self.loader.load()
        self._ensure_resource_exists(package, resource_name)
        rows = extract_rows(package, resource_name, limit_rows=limit_rows)
        return to_jsonable(
            {
                "resource": resource_name,
                "count": len(rows),
                "rows": rows,
            }
        )

    def get_customer_transactions(self, customer_id: int) -> dict[str, object]:
        if customer_id <= 0:
            raise ValueError("customer_id must be a positive integer")

        package = self.loader.load()
        rows = extract_transactions_by_customer(package, customer_id)
        return to_jsonable(
            {
                "resource": "transactions_by_customer",
                "customer_id": customer_id,
                "count": len(rows),
                "rows": rows,
            }
        )

    def _ensure_resource_exists(self, package: Package, resource_name: str) -> None:
        if resource_name not in resource_names(package):
            raise ValueError(f'unknown resource "{resource_name}"')

    def _validate_limit(self, limit_rows: int | None) -> None:
        if limit_rows is None:
            return
        if limit_rows <= 0:
            raise ValueError("limit_rows must be a positive integer")
        if limit_rows > 1000:
            raise ValueError("limit_rows cannot exceed 1000")
