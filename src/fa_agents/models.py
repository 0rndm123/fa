"""Typed public interface to a standalone financial research engine."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class AssetClass(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    FX = "fx"
    INDEX = "index"
    OTHER = "other"


class ResearchRequest(BaseModel):
    symbol: str = Field(min_length=1)
    asset_class: AssetClass
    exchange: str | None = None
    instrument_id: str | None = None
    question: str = "Provide a source-backed financial research report."
    horizon: Literal["short", "medium", "long"] = "medium"
    as_of: datetime | None = None
    include_agents: list[str] | None = None
    exclude_agents: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def clean_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol:
            raise ValueError("symbol cannot be blank")
        return symbol


class Evidence(BaseModel):
    source_id: str
    source_name: str
    source_url: str
    retrieved_at: datetime
    published_at: datetime | None = None
    observed_at: datetime | None = None
    text_excerpt: str | None = None
    is_synthetic: bool = False


AgentStatus = Literal["completed", "partial", "no_data", "not_implemented", "failed"]
ReportStatus = Literal["completed", "partial", "not_ready", "failed"]


class FinancialObservation(BaseModel):
    metric: str
    period_end: str
    value: float
    unit: str = "USD"
    source_id: str


class AgentResult(BaseModel):
    agent_id: str
    status: AgentStatus
    summary: str = ""
    claims: list[str] = Field(default_factory=list)
    metrics: dict[str, float | str | None] = Field(default_factory=dict)
    observations: list[FinancialObservation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    schema_version: str = "0.3"
    request: ResearchRequest
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ReportStatus
    data_mode: Literal["live", "demo"] = "live"
    planned_agents: list[str] = Field(default_factory=list)
    results: list[AgentResult] = Field(default_factory=list)
    summary: str = ""
    llm_commentary: str | None = None
    warnings: list[str] = Field(default_factory=list)
