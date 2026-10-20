import pytest

pytest.importorskip("langgraph")

from fa_agents.graph import build_graph


def test_graph_runs_without_claiming_financial_research():
    report = build_graph().invoke(
        {"request": {"symbol": "NVDA", "asset_class": "equity"}}
    )["report"]
    assert report["status"] == "not_ready"
    assert report["results"]
    assert all(item["status"] == "not_implemented" for item in report["results"])
    assert report["warnings"]


def test_graph_handles_no_specialists():
    report = build_graph().invoke(
        {"request": {"symbol": "TEST", "asset_class": "other", "include_agents": []}}
    )["report"]
    assert report["status"] == "not_ready"
    assert report["results"] == []
