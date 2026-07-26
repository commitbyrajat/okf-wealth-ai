from __future__ import annotations

import logging
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from .resource_service import DatapackageResourceService

logger = logging.getLogger(__name__)


def create_mcp_server(
    service: DatapackageResourceService | None = None,
) -> FastMCP:
    resource_service = service or DatapackageResourceService()
    mcp = FastMCP(
        "OKF Wealth Resources",
        instructions=(
            "Read-only tools for inspecting and extracting rows from the "
            "OKF wealth management Frictionless datapackage."
        ),
    )

    @mcp.tool(
        name="list_datapackage_resources",
        description=(
            "List every resource declared in the OKF wealth management "
            "datapackage, including field names and SQL format metadata."
        ),
        annotations={"readOnlyHint": True},
    )
    def list_datapackage_resources() -> list[dict[str, object]]:
        logger.info("MCP tool called tool=list_datapackage_resources")
        return resource_service.list_resources()

    @mcp.tool(
        name="get_resource_schema",
        description=(
            "Return the Frictionless schema and SQL dialect metadata for one "
            "datapackage resource."
        ),
        annotations={"readOnlyHint": True},
    )
    def get_resource_schema(
        resource_name: Annotated[
            str,
            Field(description="Name of the datapackage resource to inspect."),
        ],
    ) -> dict[str, object]:
        logger.info(
            "MCP tool called tool=get_resource_schema resource_name=%s",
            resource_name,
        )
        return resource_service.get_resource_schema(resource_name)

    @mcp.tool(
        name="read_resource_rows",
        description=(
            "Read rows from any OKF datapackage resource. Use limit_rows to "
            "keep responses concise."
        ),
        annotations={"readOnlyHint": True},
    )
    def read_resource_rows(
        resource_name: Annotated[
            str,
            Field(description="Name of the datapackage resource to read."),
        ],
        limit_rows: Annotated[
            int,
            Field(
                description="Maximum number of rows to return, from 1 to 1000.",
                ge=1,
                le=1000,
            ),
        ] = 100,
    ) -> dict[str, object]:
        logger.info(
            "MCP tool called tool=read_resource_rows resource_name=%s limit_rows=%s",
            resource_name,
            limit_rows,
        )
        return resource_service.read_resource_rows(
            resource_name,
            limit_rows=limit_rows,
        )

    @mcp.tool(
        name="get_customer_transactions",
        description=(
            "Return all transaction rows for one customer by applying a "
            "customer_id filter to the transactions_by_customer resource."
        ),
        annotations={"readOnlyHint": True},
    )
    def get_customer_transactions(
        customer_id: Annotated[
            int,
            Field(
                description="Positive customer id used to filter transactions.",
                ge=1,
            ),
        ],
    ) -> dict[str, object]:
        logger.info(
            "MCP tool called tool=get_customer_transactions customer_id=%s",
            customer_id,
        )
        return resource_service.get_customer_transactions(customer_id)

    return mcp
