from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = AGENT_ROOT / ".env"


def load_agent_env() -> None:
    load_dotenv(ENV_FILE, override=False)


load_agent_env()


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    model: str = Field(
        default="openai:gpt-5-mini",
        validation_alias="OKF_AGENT_MODEL",
        description="Pydantic AI model id used by the OKF agent.",
    )
    mcp_url: str = Field(
        default="http://127.0.0.1:8000/mcp/",
        validation_alias="OKF_MCP_URL",
        description="Streamable HTTP MCP endpoint exposed by okf_exec.",
    )
    api_base_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias="OKF_API_BASE_URL",
        description="Base URL for non-MCP OKF FastAPI endpoints.",
    )
    memory_dsn: str = Field(
        default="postgresql://okf_agent:okf_agent_password@127.0.0.1:5433/"
        "okf_agent_memory",
        validation_alias="OKF_AGENT_MEMORY_DSN",
        description="Postgres DSN used by Pydantic AI Harness memory.",
    )
    memory_min_size: int = Field(
        default=1,
        ge=1,
        validation_alias="OKF_AGENT_MEMORY_MIN_SIZE",
        description="Minimum asyncpg pool size for agent memory.",
    )
    memory_max_size: int = Field(
        default=5,
        ge=1,
        validation_alias="OKF_AGENT_MEMORY_MAX_SIZE",
        description="Maximum asyncpg pool size for agent memory.",
    )
    request_timeout_seconds: float = Field(
        default=20.0,
        gt=0,
        validation_alias="OKF_AGENT_REQUEST_TIMEOUT_SECONDS",
        description="HTTP timeout for local OKF API calls.",
    )
    model_request_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
        validation_alias="OKF_AGENT_MODEL_REQUEST_TIMEOUT_SECONDS",
        description="Maximum seconds to wait for one model provider request.",
    )
    run_timeout_seconds: float = Field(
        default=180.0,
        gt=0,
        validation_alias="OKF_AGENT_RUN_TIMEOUT_SECONDS",
        description="Maximum seconds to wait for a full agent run.",
    )
    max_model_requests: int = Field(
        default=8,
        ge=1,
        validation_alias="OKF_AGENT_MAX_MODEL_REQUESTS",
        description="Maximum model requests allowed in one agent run.",
    )
    max_tool_calls: int = Field(
        default=16,
        ge=1,
        validation_alias="OKF_AGENT_MAX_TOOL_CALLS",
        description="Maximum tool calls allowed in one agent run.",
    )
    max_output_tokens: int = Field(
        default=4_000,
        ge=1,
        validation_alias="OKF_AGENT_MAX_OUTPUT_TOKENS",
        description="Maximum output tokens requested from the model.",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="OKF_AGENT_LOG_LEVEL",
        description="Python logging level for okf_agent.",
    )
