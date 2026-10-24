"""Agent registry and deterministic first-release orchestration policy."""
from __future__ import annotations
from .models import AssetClass, ResearchRequest

SPECIALISTS: dict[str, str] = {
    "filings": "Corporate filings and disclosures",
    "fundamental": "Financial statements, profitability and cash flow",
    "valuation": "Valuation models and sensitivity",
    "industry": "Industry and competitors",
    "macro": "Economic and monetary conditions",
    "news": "News metadata and catalysts",
    "technical": "Price/indicator structure",
    "sentiment": "Positioning and flows",
    "crypto_onchain": "Crypto tokenomics and on-chain",
    "etf": "ETF structure and tracking",
    "backtest": "Quantitative verification",
    "risk": "Review and challenge",
}
_DEFAULT = {
    AssetClass.EQUITY: ("filings", "fundamental", "news", "technical", "risk"),
    AssetClass.ETF: ("etf", "news", "technical", "risk"),
    AssetClass.CRYPTO: ("crypto_onchain", "news", "technical", "risk"),
    AssetClass.COMMODITY: ("macro", "news", "technical", "risk"),
    AssetClass.FX: ("macro", "news", "technical", "risk"),
    AssetClass.INDEX: ("macro", "news", "technical", "risk"),
    AssetClass.OTHER: ("news", "risk"),
}


def choose_agents(request: ResearchRequest) -> list[str]:
    selected = list(_DEFAULT[request.asset_class]) if request.include_agents is None else request.include_agents
    unknown = (set(selected) | set(request.exclude_agents)) - SPECIALISTS.keys()
    if unknown:
        raise ValueError(f"Unknown agent(s): {', '.join(sorted(unknown))}")
    excluded = set(request.exclude_agents)
    return list(dict.fromkeys(a for a in selected if a not in excluded))
