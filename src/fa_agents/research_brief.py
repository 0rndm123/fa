"""Grounded research brief assembled from the independent FA_Agent specialists.

The brief does not perform trades, retrieve extra data or make investment
recommendations. It only links source-backed observations to unresolved checks.
"""
from __future__ import annotations

import re
import unicodedata
from math import isfinite

from .models import (AgentResult, CriticalReview, EvidencePoint, ResearchBrief,
                     ResearchGap, ResearchRequest)


def _words(text: str) -> set[str]:
    ascii_text = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(ch for ch in ascii_text if not unicodedata.combining(ch))
    return set(re.findall(r"[a-z]+", ascii_text))


def _objective(question: str) -> str:
    words = _words(question)
    if words & {"comprar", "vender", "investir", "investimento", "buy", "sell",
                "invest", "investment", "entrada", "entrar", "long", "short",
                "posicao", "position", "oportunidade", "opportunity"}:
        return "investment_decision"
    if words & {"grafico", "tecnica", "tecnico", "technical", "rsi", "ema",
                "sma", "suporte", "support", "trend", "tendencia"}:
        return "technical_research"
    if words & {"cot", "funding", "derivados", "derivatives", "positioning",
                "posicionamento", "futuros"}:
        return "positioning_research"
    if words & {"balanco", "divida", "liquidez", "financeiro", "financial",
                "fundamental", "receitas", "revenue", "lucro", "lucros",
                "debt", "margin", "margem"}:
        return "financial_research"
    return "general_research"


def build_research_brief(request: ResearchRequest, results: list[AgentResult],
                         review: CriticalReview, *, demo: bool = False) -> ResearchBrief:
    """Prepare an auditable research handoff; no speculative bull/bear narrative."""
    objective = _objective(request.question)
    points: list[EvidencePoint] = []
    gaps: list[ResearchGap] = []
    seen: set[str] = set()
    by_agent = {r.agent_id: r for r in results}

    def gap(category: str, priority: str, reason: str, next_action: str,
            agent: str | None = None) -> None:
        if category in seen:
            return
        seen.add(category)
        gaps.append(ResearchGap(
            category=category, priority=priority, reason=reason,
            next_action=next_action, suggested_agent=agent,
        ))

    # Use the observation's own source_id, never a nearby unrelated source
    # or all evidence records from the same agent.
    for r in results:
        if r.status not in {"completed", "partial"}:
            continue
        source_ids = {e.source_id for e in r.evidence}
        for observation in sorted(r.observations,
                                  key=lambda x: (x.period_end, x.metric), reverse=True):
            if observation.source_id not in source_ids:
                continue
            if not isfinite(observation.value):
                continue
            if len([p for p in points if p.agent_id == r.agent_id]) >= 2:
                break
            points.append(EvidencePoint(
                agent_id=r.agent_id, source_id=observation.source_id,
                metric=observation.metric, period=observation.period_end,
                value=observation.value, unit=observation.unit,
            ))
            if len(points) >= 8:
                break
        if len(points) >= 8:
            break

    serious = [f for f in review.findings if f.severity == "high"]
    if serious:
        gap("evidence_quality", "high",
            "The critical reviewer identified provenance, temporal or consistency issues.",
            "Resolve the critical findings and verify the affected original source records.")

    if objective == "investment_decision":
        gap("valuation", "high",
            "No independently verified valuation, fair value or return/risk model is available.",
            "Obtain a dated valuation and independent scenario assumptions before considering an entry.")
        gap("risk_reward", "high",
            "The available specialists do not establish a verified entry, stop or risk/reward profile.",
            "Specify investment horizon, acceptable loss, and validate market prices and liquidity.",
            "technical" if request.asset_class.value in {"equity", "crypto", "etf"} else None)

    if request.asset_class.value == "equity":
        financials = [r for r in results if r.agent_id in
                      {"financial_data", "fundamental", "financial_performance"}]
        if objective in {"investment_decision", "financial_research"} and not any(
            r.evidence and r.status in {"completed", "partial"} for r in financials
        ):
            gap("financial_statements", "high",
                "No usable sourced financial statements were obtained for this company.",
                "Verify recent company filings and period-matched revenue, profitability and cash flow.",
                "financial_data")
        debt = by_agent.get("debt_liquidity")
        if objective in {"investment_decision", "financial_research"} and (
            debt is None or debt.status not in {"completed", "partial"} or not debt.evidence
        ):
            gap("liquidity", "medium",
                "Debt and liquidity have not been established from dated financial records.",
                "Check balance sheet debt maturities, cash and current liabilities.",
                "debt_liquidity")
        filing = by_agent.get("filings")
        if filing and filing.status == "partial":
            gap("filing_text", "medium",
                "Filing metadata was located, but the full disclosures were not verified.",
                "Read the original filing text and notes before interpreting its contents.")
    tech = by_agent.get("technical")
    if objective in {"investment_decision", "technical_research"}:
        if tech is None or tech.status in {"failed", "no_data", "not_implemented"}:
            gap("price_history", "high",
                "No usable source-backed price history supports technical conclusions.",
                "Obtain correctly dated and adjusted price history for the intended timeframe.",
                "technical")
        elif any("intraday" in text.lower() or "not necessarily adjusted" in text.lower()
                 for text in [tech.summary, *tech.limitations]):
            gap("timeframe", "medium",
                "Available price observations may be intraday or unadjusted.",
                "Confirm the market, adjusted prices and bar timeframe before applying indicators.",
                "technical")
    news = by_agent.get("news")
    if news and news.status == "partial" and objective == "investment_decision":
        gap("news_verification", "medium",
            "News headlines are not verified full articles or primary disclosures.",
            "Verify material claims using primary sources before relying on catalysts.")
    if objective == "positioning_research" and not any(
        r.evidence for r in results if r.agent_id in {"cot", "crypto_derivatives"}
    ):
        gap("positioning", "high",
            "No usable dated futures positioning observations were retrieved.",
            "Check the exact contract, report date and original CFTC or exchange records.",
            "cot" if request.asset_class.value != "crypto" else "crypto_derivatives")
    if not any(r.evidence for r in results):
        gap("data_availability", "high",
            "The investigation contains no dated source records.",
            "Configure a relevant supported data source or supply verified records.")

    if demo:
        gap("synthetic_data", "high",
            "Demo observations are synthetic fixtures, not live market evidence.",
            "Repeat the investigation in Live mode with original sources.")

    gaps.sort(key=lambda g: {"high": 0, "medium": 1, "low": 2}[g.priority])
    return ResearchBrief(
        objective=objective,
        evidence_points=points,
        open_questions=gaps[:8],
        assessment=("insufficient_evidence" if not points else "descriptive_only"),
        method="deterministic, original-source linked and question-specific",
    )
