from __future__ import annotations

import logging
import os
import time
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import RedirectResponse

from .instructions import DEFAULT_INSTRUCTIONS_URL, InstructionReader
from .logging_config import configure_logging
from .mcp_server import create_mcp_server
from .resource_service import DatapackageResourceService

logger = logging.getLogger(__name__)


def create_app(
    service: DatapackageResourceService | None = None,
    instruction_reader: InstructionReader | None = None,
) -> FastAPI:
    configure_logging(os.environ.get("OKF_LOG_LEVEL", "INFO"))
    resource_service = service or DatapackageResourceService()
    instructions = instruction_reader or InstructionReader()
    mcp = create_mcp_server(resource_service)
    mcp_app = mcp.http_app(path="/")

    app = FastAPI(
        title="OKF Wealth Resource API",
        version="0.1.0",
        description=(
            "Read-only FastAPI endpoints for resources declared in the OKF "
            "wealth management Frictionless datapackage. FastMCP is mounted "
            "at /mcp."
        ),
        lifespan=mcp_app.lifespan,
    )

    @app.middleware("http")
    async def log_http_request(request: Request, call_next):
        start_time = time.perf_counter()
        logger.info(
            "request started method=%s path=%s", request.method, request.url.path
        )
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "request failed method=%s path=%s elapsed_ms=%.2f",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request completed method=%s path=%s status_code=%s elapsed_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @app.get(
        "/",
        operation_id="root",
        summary="API root",
        description="Redirect browser visits from the API root to Swagger UI.",
        include_in_schema=False,
    )
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get(
        "/health",
        operation_id="health_check",
        summary="Health check",
        description="Return a simple status payload for API health checks.",
    )
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/resources",
        operation_id="list_resources",
        summary="List datapackage resources",
        description=(
            "List all resources declared in datapackage.json with field names "
            "and SQL metadata."
        ),
    )
    def list_resources() -> list[dict[str, object]]:
        logger.info("listing datapackage resources")
        return _call_service(resource_service.list_resources)

    @app.get(
        "/resources/{resource_name}/schema",
        operation_id="get_resource_schema",
        summary="Get resource schema",
        description=(
            "Return the Frictionless schema and SQL dialect metadata for one "
            "datapackage resource."
        ),
    )
    def get_resource_schema(
        resource_name: Annotated[
            str,
            Path(description="Name of the datapackage resource to inspect."),
        ],
    ) -> dict[str, object]:
        logger.info("reading resource schema resource_name=%s", resource_name)
        return _call_service(resource_service.get_resource_schema, resource_name)

    @app.get(
        "/resources/{resource_name}/rows",
        operation_id="read_resource_rows",
        summary="Read resource rows",
        description=(
            "Read rows from any resource declared in datapackage.json. Use "
            "limit_rows to keep responses bounded."
        ),
    )
    def read_resource_rows(
        resource_name: Annotated[
            str,
            Path(description="Name of the datapackage resource to read."),
        ],
        limit_rows: Annotated[
            int,
            Query(
                description="Maximum number of rows to return, from 1 to 1000.",
                ge=1,
                le=1000,
            ),
        ] = 100,
    ) -> dict[str, object]:
        logger.info(
            "reading resource rows resource_name=%s limit_rows=%s",
            resource_name,
            limit_rows,
        )
        return _call_service(
            resource_service.read_resource_rows,
            resource_name,
            limit_rows=limit_rows,
        )

    @app.get(
        "/customers/{customer_id}/transactions",
        operation_id="get_customer_transactions",
        summary="Get customer transactions",
        description=(
            "Return all transaction rows for one customer by applying a "
            "customer_id filter to the transactions_by_customer resource."
        ),
    )
    def get_customer_transactions(
        customer_id: Annotated[
            int,
            Path(
                description="Positive customer id used to filter transactions.",
                ge=1,
            ),
        ],
    ) -> dict[str, object]:
        logger.info("reading customer transactions customer_id=%s", customer_id)
        return _call_service(resource_service.get_customer_transactions, customer_id)

    @app.get(
        "/instructions",
        operation_id="read_instructions",
        summary="Read OKF markdown instructions",
        description=(
            "Read an OKF markdown instruction document from a URL using "
            "Frictionless TextResource. GitHub blob URLs are normalized to "
            "raw markdown URLs, and markdown links are returned so callers can "
            "choose the next OKF document to read."
        ),
    )
    def read_instructions(
        url: Annotated[
            str,
            Query(
                description=(
                    "HTTP(S) markdown URL to read. Defaults to the OKF wealth "
                    "knowledge index."
                ),
            ),
        ] = DEFAULT_INSTRUCTIONS_URL,
        include_linked: Annotated[
            bool,
            Query(
                description=(
                    "When true, also read linked markdown documents discovered "
                    "in the requested document."
                ),
            ),
        ] = False,
        max_depth: Annotated[
            int,
            Query(
                description="Maximum markdown-link traversal depth, from 0 to 2.",
                ge=0,
                le=2,
            ),
        ] = 1,
    ) -> dict[str, object]:
        logger.info(
            "reading instructions url=%s include_linked=%s max_depth=%s",
            url,
            include_linked,
            max_depth,
        )
        return _call_instruction_reader(
            instructions.read,
            url,
            include_linked=include_linked,
            max_depth=max_depth,
        )

    app.mount("/mcp", mcp_app)
    return app


def _call_service(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as exception:
        raise HTTPException(status_code=404, detail=str(exception)) from exception
    except RuntimeError as exception:
        raise HTTPException(status_code=500, detail=str(exception)) from exception


def _call_instruction_reader(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as exception:
        raise HTTPException(status_code=400, detail=str(exception)) from exception
    except RuntimeError as exception:
        raise HTTPException(status_code=502, detail=str(exception)) from exception


app = create_app()


def main() -> None:
    host = os.environ.get("OKF_API_HOST", "127.0.0.1")
    port = int(os.environ.get("OKF_API_PORT", "8000"))
    uvicorn.run("okf_exec.api:app", host=host, port=port, reload=False)
