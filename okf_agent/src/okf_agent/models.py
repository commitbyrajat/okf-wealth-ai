from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import httpx
from pydantic import BaseModel, Field, model_validator


@dataclass
class OkfAgentDeps:
    session_id: str
    http_client: httpx.AsyncClient
    consulted_instruction_urls: set[str] = field(default_factory=set)


class InstructionLink(BaseModel):
    title: str = Field(description="Markdown link title found in an OKF document.")
    url: str = Field(description="Original markdown link target.")
    resolved_url: str = Field(description="Absolute URL resolved for reading.")


class InstructionDocument(BaseModel):
    url: str = Field(description="Requested instruction URL.")
    resolved_url: str = Field(description="Resolved URL used to read markdown.")
    content: str = Field(description="Markdown instruction content.")
    links: list[InstructionLink] = Field(
        default_factory=list,
        description="Markdown documents referenced by this instruction document.",
    )
    linked_documents: list["InstructionDocument"] = Field(
        default_factory=list,
        description="Instruction documents read through linked markdown references.",
    )


class ConsultedInstruction(BaseModel):
    title: str = Field(
        min_length=1,
        description="Human-readable OKF instruction document title.",
    )
    url: str = Field(description="Resolved OKF markdown URL consulted by the agent.")
    role: Literal["index", "scenario_rule", "supporting"] = Field(
        description="How this instruction document was used in the answer.",
    )
    reason: str = Field(
        min_length=1,
        description="Why this instruction document was relevant.",
    )


class DataSource(BaseModel):
    name: str = Field(
        min_length=1,
        description="MCP tool, FastAPI endpoint, or memory source used.",
    )
    source_type: Literal["mcp_tool", "fastapi_endpoint", "memory", "assumption"] = (
        Field(
            description="Kind of source used for this answer.",
        )
    )
    reason: str = Field(
        min_length=1,
        description="Why this source was needed.",
    )


class OkfAgentAnswer(BaseModel):
    """Final structured answer returned by the OKF wealth management agent."""

    scenario: Literal[
        "holding_calculation",
        "redemption_optimization",
        "customer_transactions",
        "resource_inspection",
        "general",
    ] = Field(description="Primary OKF scenario used to frame the answer.")
    answer: str = Field(min_length=1, description="Final user-facing answer.")
    instruction_urls: list[str] = Field(
        min_length=1,
        description="OKF markdown instruction URLs consulted before answering.",
    )
    consulted_instructions: list[ConsultedInstruction] = Field(
        min_length=1,
        description="Detailed record of OKF instruction documents consulted.",
    )
    data_sources: list[DataSource] = Field(
        default_factory=list,
        description="MCP resources, API endpoints, or memory sources used.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Relevant assumptions or constraints that affect the answer.",
    )

    @model_validator(mode="after")
    def validate_instruction_consistency(self) -> OkfAgentAnswer:
        consulted_urls = [
            instruction.url for instruction in self.consulted_instructions
        ]
        missing_urls = set(consulted_urls) - set(self.instruction_urls)
        if missing_urls:
            raise ValueError(
                "instruction_urls must include every consulted instruction URL"
            )
        requires_scenario_document = self.scenario != "general"
        has_scenario_rule = any(
            instruction.role == "scenario_rule"
            for instruction in self.consulted_instructions
        )
        if requires_scenario_document and not has_scenario_rule:
            raise ValueError(
                "at least one consulted instruction must be a scenario_rule"
            )
        return self
