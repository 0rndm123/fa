"""Offline unit and graph tests for bounded standalone FA research coordination."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from fa_agents.agents import Services
from fa_agents.coordinator import assess_followups, critical_review, initial_plan
from fa_agents.graph import build_graph
from fa_agents.models import AgentResult, CriticalReview, Evidence, FinancialObservation, ResearchRequest


def _request(**kwargs):
    return ResearchRequest(symbol="NVDA", asset_class="equity",
                           question="Investigate financial and governance risks", **kwargs)


def _partial(agent):
    return AgentResult(agent_id=agent, status="partial", summary="Source discovery only.")


def _evidence(source_id, year=2025, *, synthetic=False):
    dt = datetime(year, 3, 1, tzinfo=timezone.utc)
    return Evidence(source_id=source_id, source_name="SEC XBRL",
                    source_url="https://www.sec.gov/filings", retrieved_at=dt,
                    published_at=dt, observed_at=dt, is_synthetic=synthetic)


def test_adaptive_coordinator_can_request_bounded_new_specialist():
    request = _request()
    original = initial_plan(["governance"], "adaptive", manual=False)
    plan = assess_followups(request, original, [_partial("governance")])
    assert plan.initial_agents == ["governance"]
    assert plan.followup_agents == ["filings"]
    assert plan.max_followup_agents == 2


def test_no_repeated_or_excluded_specialists_and_manual_selection_is_respected():
    request = _request(exclude_agents=["filings"])
    plan = initial_plan(["governance"], "adaptive", manual=False)
    assert assess_followups(request, plan, [_partial("governance")]).followup_agents == []
    manual = initial_plan(["governance"], "adaptive", manual=True)
    assert assess_followups(_request(), manual, [_partial("governance")], manual=True).followup_agents == []
    assert assess_followups(_request(), plan, [_partial("governance")], demo=True).followup_agents == []
    assert assess_followups(_request(), initial_plan(["governance"], "standard", False),
                            [_partial("governance")]).followup_agents == []


def test_assisted_planning_invalid_selection_falls_back_to_allowlist():
    plan = initial_plan(["governance"], "assisted", manual=False)
    with patch("fa_agents.coordinator._llm_choose_followups", return_value=["trade_execution"]):
        result = assess_followups(_request(), plan, [_partial("governance")])
    assert result.followup_agents == ["filings"]
    assert any("fallback" in n for n in result.notes)
    with patch("fa_agents.coordinator._llm_choose_followups", side_effect=RuntimeError("API unavailable")):
        result = assess_followups(_request(), plan, [_partial("governance")])
    assert result.followup_agents == ["filings"]


def test_crypto_does_not_start_unrelated_sec_followups():
    req = ResearchRequest(symbol="BTCUSDT", asset_class="crypto")
    plan = initial_plan(["news", "technical"], "adaptive", manual=False)
    assert assess_followups(req, plan, [_partial("news"), _partial("technical")]).followup_agents == []


def test_critical_review_finds_missing_provenance_and_future_evidence():
    request = _request(as_of=datetime(2024, 12, 31, tzinfo=timezone.utc))
    result = AgentResult(agent_id="financial_data", status="completed",
                         observations=[FinancialObservation(metric="revenue", period_end="2024-12-31",
                                                            value=100.0, source_id="not-there")],
                         evidence=[_evidence("late-2025", year=2025)])
    review = critical_review(request, [result])
    assert review.status == "caution"
    assert {x.category for x in review.findings} >= {"provenance", "temporal"}
    assert "not-there" in next(x for x in review.findings
                               if x.category == "provenance").source_ids


def test_critical_reviewer_checks_matching_periods_not_different_years():
    metrics = {"revenue_usd": 100.0, "revenue_period": "2024-12-31"}
    first = AgentResult(agent_id="fundamental", status="completed",
                        metrics=metrics, evidence=[_evidence("sec-2024")])
    second = AgentResult(agent_id="financial_data", status="completed",
                         metrics={"revenue_usd": 125.0, "revenue_period": "2024-12-31"},
                         evidence=[_evidence("sec-2024-other")])
    review = critical_review(_request(), [first, second])
    assert any(f.category == "consistency" and f.severity == "high"
               for f in review.findings)
    different = second.model_copy(update={
        "metrics": {"revenue_usd": 125.0, "revenue_period": "2023-12-31"}
    })
    review_other_year = critical_review(_request(), [first, different])
    assert not any(f.category == "consistency" for f in review_other_year.findings)


def test_insufficient_review_does_not_invent_negative_facts():
    review = critical_review(_request(), [AgentResult(agent_id="valuation",
                                                      status="not_implemented")])
    assert isinstance(review, CriticalReview)
    assert review.status == "insufficient"
    assert not any(f.category == "consistency" for f in review.findings)


def test_langgraph_runs_at_most_one_new_followup_round_without_retries():
    request = _request(include_agents=["governance"])
    calls = []

    def fake_worker(name, req, svc):
        calls.append(name)
        return _partial(name)

    with patch("fa_agents.graph.run_specialist", side_effect=fake_worker):
        raw = build_graph(Services.build("live")).invoke({
            "request": request.model_dump(mode="json"),
            "automatic_selection": True,
        })
    report = raw["report"]
    assert calls == ["governance", "filings"]
    assert report["research_plan"]["followup_agents"] == ["filings"]
    assert report["planned_agents"] == ["governance", "filings"]
    assert "critical_review" in report


def test_graph_explicit_manual_selection_stops_delegation():
    request = _request(include_agents=["governance"])
    with patch("fa_agents.graph.run_specialist", return_value=_partial("governance")) as worker:
        raw = build_graph(Services.build("live")).invoke({
            "request": request.model_dump(mode="json"),
            "automatic_selection": False,
        })
    assert worker.call_count == 1
    assert raw["report"]["research_plan"]["followup_agents"] == []
