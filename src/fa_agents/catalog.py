"""Declared specialist capabilities and deterministic initial routing."""
from __future__ import annotations

from .models import AssetClass, ResearchRequest

SPECIALISTS: dict[str, str] = {
    "filings": "Official company filings and footnotes",
    "fundamental": "Financial statement quality and performance",
    "valuation": "Company valuation and scenario sensitivity",
    "industry": "Competitive and sector analysis",
    "macro": "Macro conditions and regime",
    "news": "Events, catalysts and current news",
    "technical": "Technical indicators and price structure",
    "sentiment": "Positioning, flows and sentiment",
    "crypto_onchain": "Crypto network and tokenomics",
    "etf": "ETF holdings, fees and structure",
    "backtest": "Reproducible strategy evidence",
    "risk": "Independent challenge and thesis invalidation",
}

_DEFAULT: dict[AssetClass, tuple[str, ...]] = {
    AssetClass.EQUITY: (
        "filings", "fundamental", "valuation", "industry", "macro",
        "news", "technical", "risk",
    ),
    AssetClass.ETF: ("etf", "industry", "macro", "news", "technical", "risk"),
    AssetClass.CRYPTO: ("crypto_onchain", "macro", "news", "sentiment", "technical", "risk"),
    AssetClass.COMMODITY: ("macro", "news", "sentiment", "technical", "risk"),
    AssetClass.FX: ("macro", "news", "sentiment", "technical", "risk"),
    AssetClass.INDEX: ("macro", "industry", "news", "technical", "risk"),
    AssetClass.OTHER: ("news", "risk"),
}


def choose_agents(request: ResearchRequest) -> list[str]:
    """Select a stable, explicit list of specialist IDs (not an LLM decision)."""
    selected = (
        list(_DEFAULT[request.asset_class])
        if request.include_agents is None
        else list(request.include_agents)
    )
    unknown = (set(selected) | set(request.exclude_agents)) - SPECIALISTS.keys()
    if unknown:
        raise ValueError(f"Unknown agent(s): {', '.join(sorted(unknown))}")
    excluded = set(request.exclude_agents)
    return list(dict.fromkeys(a for a in selected if a not in excluded))
