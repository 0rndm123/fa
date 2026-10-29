"""Research briefs must stay source-linked, time-safe and non-prescriptive."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from fa_agents.models import (
    AgentResult, CriticalFinding, CriticalReview, Evidence, FinancialObservation,
    ResearchRequest,
)
from fa_agents.research_brief import build_research_brief
from fa_agents.webapp import app


def req(question="Devo comprar a NVIDIA?", **kwargs):
    return ResearchRequest(symbol="NVDA", asset_class="equity", question=question, **kwargs)


def evidence(id, year=2024, synthetic=False):
    dt = datetime(year, 3, 1, tzinfo=timezone.utc)
    return Evidence(source_id=id, source_name="SEC", source_url="https://data.sec.gov/source",
                    retrieved_at=dt, published_at=dt, observed_at=dt, is_synthetic=synthetic)


def partial(agent, *, evidences=None, observations=None, metrics=None):
    return AgentResult(agent_id=agent, status="partial", evidence=evidences or [],
                       observations=observations or [], metrics=metrics or {})


def test_investment_question_identifies_missing_valuation_and_risk():
    report = build_research_brief(
        req("Será uma boa oportunidade para uma posição longa?"),
        [partial("financial_data", evidences=[evidence("sec")])],
        CriticalReview(status="clear"),
    )
    assert report.objective == "investment_decision"
    assert report.assessment == "descriptive_only"
    categories = {x.category for x in report.open_questions}
    assert {"valuation", "risk_reward", "liquidity", "price_history"} <= categories
    assert all("Buy now" not in x.next_action for x in report.open_questions)


def test_evidence_points_are_source_id_matched_not_guesswork():
    result = partial("financial_data", evidences=[evidence("sec-1")], observations=[
        FinancialObservation(metric="revenue", period_end="2024-01-01",
                             value=100.0, unit="USD", source_id="sec-1"),
        FinancialObservation(metric="cash", period_end="2024-01-01",
                             value=12.0, unit="USD", source_id="unknown"),
    ])
    report = build_research_brief(req("Analisa a receita"), [result],
                                 CriticalReview(status="clear"))
    assert len(report.evidence_points) == 1
    assert report.evidence_points[0].source_id == "sec-1"
    assert report.evidence_points[0].value == 100.0
    assert report.assessment == "descriptive_only"


def test_metrics_alone_do_not_create_attributed_observations():
    result = partial("fundamental", evidences=[evidence("filing")],
                     metrics={"revenue_usd": 150.0})
    report = build_research_brief(req("Receita da empresa"), [result],
                                 CriticalReview(status="clear"))
    assert report.evidence_points == []
    assert report.assessment == "descriptive_only"


def test_historical_research_excludes_future_publications_and_periods():
    request = req("Analisa os resultados", as_of=datetime(2024, 12, 31,
                                                          tzinfo=timezone.utc))
    result = partial("financial_data", evidences=[evidence("future", 2025),
                                                   evidence("past", 2024)], observations=[
        FinancialObservation(metric="revenue", period_end="2024-01-01",
                             value=999.0, source_id="future"),
        FinancialObservation(metric="cash", period_end="2025-01-01",
                             value=222.0, source_id="past"),
        FinancialObservation(metric="revenue", period_end="2024-01-01",
                             value=100.0, source_id="past"),
    ])
    report = build_research_brief(request, [result],
                                 CriticalReview(status="clear"))
    assert len(report.evidence_points) == 1
    assert report.evidence_points[0].value == 100.0
    assert report.evidence_points[0].source_id == "past"


def test_only_future_sources_are_insufficient_at_asof():
    request = req("Analisa a saúde financeira",
                  as_of=datetime(2023, 12, 31, tzinfo=timezone.utc))
    report = build_research_brief(
        request, [partial("financial_data", evidences=[evidence("postcut", 2025)])],
        CriticalReview(status="caution"),
    )
    assert report.assessment == "insufficient_evidence"
    assert "data_availability" in {x.category for x in report.open_questions}


def test_adverse_metrics_prompt_checks_not_predictions():
    result = partial("fundamental", evidences=[evidence("filing")],
                     metrics={"fcf_proxy_usd": -150.0,
                              "annual_revenue_growth_pct": -2.0})
    report = build_research_brief(req("Analisa a saúde financeira"), [result],
                                 CriticalReview(status="clear"))
    categories = {x.category for x in report.open_questions}
    assert {"negative_fcf", "declining_revenue"} <= categories
    assert all("sell" not in g.next_action.lower() for g in report.open_questions)


def test_critical_failures_are_promoted_to_first_priority():
    audit = CriticalReview(status="caution", findings=[CriticalFinding(
        severity="high", category="consistency",
        message="Revenue differs for matching periods", agent_ids=["fundamental", "financial_data"]
    )])
    report = build_research_brief(req("Receita da NVIDIA"), [], audit)
    assert report.open_questions[0].category == "evidence_quality"
    assert report.open_questions[0].priority == "high"


def test_crypto_positioning_identifies_missing_exchange_observations():
    request = ResearchRequest(symbol="BTCUSDT", asset_class="crypto",
                              question="Analisa o funding dos derivados")
    report = build_research_brief(request, [partial("crypto_derivatives")],
                                 CriticalReview(status="insufficient"))
    assert report.objective == "positioning_research"
    assert any(x.suggested_agent == "crypto_derivatives"
               for x in report.open_questions)


def test_demo_api_includes_brief_but_no_live_recommendation():
    r = TestClient(app).post("/api/analyze", json={
        "symbol": "DEMO", "asset_class": "equity", "mode": "demo",
        "question": "Devo investir nesta empresa?", "agents": ["financial_data", "risk"],
    })
    assert r.status_code == 200, r.text
    brief = r.json()["report"]["research_brief"]
    assert brief["assessment"] == "descriptive_only"
    assert brief["objective"] == "investment_decision"
    assert "synthetic_data" in {x["category"] for x in brief["open_questions"]}
    assert brief["evidence_points"]
    assert all(x["source_id"] for x in brief["evidence_points"])
