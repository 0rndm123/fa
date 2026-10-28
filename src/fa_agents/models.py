"""Typed public interface to a standalone financial research engine."""
from __future__ import annotations
from datetime import datetime, timezone, date
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
    cot_market_code: str | None = None
    cot_report_type: Literal["tff","disaggregated","legacy"] | None = None

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


class CotMarket(BaseModel):
    code: str
    name: str
    market: str


class CotPosition(BaseModel):
    group: str
    long: int
    short: int
    net: int
    net_pct_oi: float
    net_wow: int | None = None


class CotWeek(BaseModel):
    report_date: date
    open_interest: int
    groups: list[CotPosition]


class CotData(BaseModel):
    report_type: Literal["tff","disaggregated","legacy"]
    source: str
    market_code: str | None = None
    market_name: str | None = None
    markets: list[CotMarket] = Field(default_factory=list)
    weeks: list[CotWeek] = Field(default_factory=list)
    latest: CotWeek | None = None
    source_url: str | None = None


class CryptoMetricPoint(BaseModel):
    metric: str
    at: datetime
    value: float
    unit: str


class CryptoDerivativesData(BaseModel):
    provider: str
    instrument: str
    market_type: str
    retrieved_at: datetime
    series: list[CryptoMetricPoint] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent_id: str
    status: AgentStatus
    summary: str = ""
    ai_commentary: str | None = None
    ai_model: str | None = None
    claims: list[str] = Field(default_factory=list)
    metrics: dict[str, float | str | None] = Field(default_factory=dict)
    observations: list[FinancialObservation] = Field(default_factory=list)
    cot: CotData | None = None
    crypto_derivatives: CryptoDerivativesData | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class PricePoint(BaseModel):
    at: datetime
    price: float


class OHLCBar(BaseModel):
    at: datetime
    open: float
    high: float
    low: float
    close: float


class MarketQuote(BaseModel):
    provider: str
    symbol: str
    instrument: str
    venue: str
    currency: str
    price: float
    at: datetime
    retrieved_at: datetime
    timestamp_kind: str
    source_url: str
    caveat: str
    previous_close: float | None = None
    history: list[PricePoint] = Field(default_factory=list)
    bars: list[OHLCBar] = Field(default_factory=list)
    bar_interval: str | None = None


class ProviderAttempt(BaseModel):
    provider: str
    status: Literal["ok", "failed", "not_configured"] = "failed"
    symbol: str
    quote: MarketQuote | None = None
    error: str | None = None


class QuoteResult(BaseModel):
    requested_symbol: str
    asset_class: str
    selected: MarketQuote | None = None
    attempts: list[ProviderAttempt] = Field(default_factory=list)


class ResearchReport(BaseModel):
    schema_version: str = "0.7"
    request: ResearchRequest
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ReportStatus
    data_mode: Literal["live", "demo"] = "live"
    planned_agents: list[str] = Field(default_factory=list)
    results: list[AgentResult] = Field(default_factory=list)
    summary: str = ""
    market_quote: QuoteResult | None = None
    llm_commentary: str | None = None
    warnings: list[str] = Field(default_factory=list)
