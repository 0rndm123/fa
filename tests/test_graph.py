from fa_agents.graph import build_graph
from fa_agents.agents import Services
from fa_agents.models import ResearchRequest


def run_demo(agents=None, as_of=None):
    request = ResearchRequest(
        symbol="DEMO", asset_class="equity", as_of=as_of, include_agents=agents
    )
    return build_graph(Services.build("demo")).invoke({
        "request": request.model_dump(mode="json")
    })["report"]


def test_end_to_end_demo_has_real_calculations():
    report = run_demo()
    result = {x["agent_id"]: x for x in report["results"]}
    assert report["data_mode"] == "demo"
    assert report["status"] == "partial"
    assert result["financial_data"]["status"] == "completed"
    assert len(result["financial_data"]["observations"]) == 8
    assert all(item["source_id"] for item in result["financial_data"]["observations"])
    assert result["fundamental"]["status"] == "completed"
    assert result["fundamental"]["metrics"]["annual_revenue_growth_pct"] == 15.0
    assert result["fundamental"]["metrics"]["fcf_proxy_usd"] == 120000.0
    assert result["filings"]["status"] == "partial"
    assert result["news"]["status"] == "partial"
    assert result["technical"]["status"] == "no_data"
    assert result["risk"]["status"] == "partial"
    assert len(report["results"]) == 6
    assert all(x["is_synthetic"] for x in result["fundamental"]["evidence"])
    assert any("SYNTHETIC" in x for x in report["warnings"])


def test_historical_information_not_used_before_publication():
    report = run_demo(["fundamental"], "2024-06-01")
    metric = report["results"][0]["metrics"]
    assert metric["revenue_usd"] == 1000000.0
    assert "annual_revenue_growth_pct" not in metric


def test_unimplemented_specialists_do_not_hallucinate():
    report = run_demo(["valuation"])
    assert report["status"] == "not_ready"
    assert report["results"][0]["status"] == "not_implemented"


def test_empty_and_risk_only_paths():
    assert run_demo([])["status"] == "not_ready"
    risk = run_demo(["risk"])
    assert len(risk["results"]) == 1
    assert risk["results"][0]["agent_id"] == "risk"
