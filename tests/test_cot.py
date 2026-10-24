"""CFTC COT specialist offline tests: source injection, market code safety, weekly trends."""
import json
from datetime import date
import pytest
from fastapi.testclient import TestClient

from fa_agents.agents import Services
from fa_agents.catalog import select_for_question
from fa_agents.cot import (
    CftcApiSource, PostgresCotSource, compute_cot, cot_specialist,
    select_cot_market, is_cot_question,
)
from fa_agents.models import ResearchRequest
from fa_agents.providers import ProviderError
from fa_agents.webapp import app


def market(code="088691"):
    return {"cftc_contract_market_code":code,
            "contract_market_name":"GOLD",
            "market_and_exchange_names":"GOLD - COMMODITY EXCHANGE INC."}


def position(day,code="088691",oi=2000,managed_long=450,managed_short=120):
    return {**market(code),
        "report_date_as_yyyy_mm_dd":day,
        "open_interest_all":str(oi),
        "prod_merc_positions_long":"500","prod_merc_positions_short":"850",
        "swap_positions_long_all":"300","swap__positions_short_all":"320",
        "m_money_positions_long_all":str(managed_long),
        "m_money_positions_short_all":str(managed_short),
        "other_rept_positions_long":"200","other_rept_positions_short":"100",
        "nonrept_positions_long_all":"50","nonrept_positions_short_all":"100"}


class MockCotSource:
    source="cftc"
    def __init__(self,candidates=None,history=None):
        self.candidates=candidates if candidates is not None else [market()]
        self.rows=history if history is not None else [
            position("2026-10-20",managed_long=450,managed_short=120),
            position("2026-10-13",managed_long=420,managed_short=140)]
        self.queries=[]

    def search(self,report,query):
        self.queries.append(("search",report,query))
        return self.candidates

    def history(self,report,code,limit):
        self.queries.append(("history",report,code,limit))
        return self.rows


def req(symbol="NVDA",q="Qual é o COT do ouro?",**kwargs):
    return ResearchRequest(symbol=symbol,asset_class="equity",question=q,**kwargs)


def test_only_explicit_cot_questions_route_to_specialist():
    assert is_cot_question("COT do ouro?")
    assert is_cot_question("Commitments of Traders para ouro")
    assert not is_cot_question("Qual é a cotação do ouro?")
    assert select_for_question(req())==["cot"]
    assert select_for_question(req(q="Analisa dívida NVDA"))!=["cot"]
    assert select_cot_market("COT Nasdaq 100","NVDA")==("tff","NASDAQ-100")
    assert select_cot_market("COT petróleo","NVDA")==("disaggregated","CRUDE OIL")


def test_individual_stock_has_no_assumed_cot_proxy(monkeypatch):
    import fa_agents.cot as module
    src=MockCotSource()
    monkeypatch.setattr(module,"get_source",lambda:src)
    result=cot_specialist(req(q="COT da NVIDIA"),Services.build())
    assert result.status=="no_data" and result.cot is None
    assert src.queries==[]
    assert "futures" in result.summary


def test_ambiguous_market_search_returns_choices_not_claims(monkeypatch):
    import fa_agents.cot as module
    src=MockCotSource(candidates=[market("088691"),market("088692")])
    monkeypatch.setattr(module,"get_source",lambda:src)
    result=cot_specialist(req(),Services.build())
    assert result.status=="partial"
    assert result.cot and len(result.cot.markets)==2
    assert not result.metrics
    assert src.queries==[("search","disaggregated","GOLD")]


def test_unique_market_retrieves_weekly_data_and_computes_net(monkeypatch):
    import fa_agents.cot as module
    src=MockCotSource()
    monkeypatch.setattr(module,"get_source",lambda:src)
    result=cot_specialist(req(),Services.build())
    assert result.status=="completed"
    assert result.cot and len(result.cot.weeks)==2
    assert result.cot.latest.report_date==date(2026,10,20)
    group=next(p for p in result.cot.latest.groups if p.group=="Managed Money")
    assert group.long==450 and group.short==120
    assert group.net==330 and group.net_pct_oi==16.5 and group.net_wow==50
    assert all(e.source_url.startswith("https://") for e in result.evidence)
    assert src.queries[1]==("history","disaggregated","088691",52)


def test_explicit_code_skips_search(monkeypatch):
    import fa_agents.cot as module
    src=MockCotSource(candidates=[market("088691"),market("088692")])
    monkeypatch.setattr(module,"get_source",lambda:src)
    result=cot_specialist(req(q="COT GOLD",cot_market_code="088691",
                                 cot_report_type="disaggregated"),Services.build())
    assert result.status=="completed"
    assert src.queries==[("history","disaggregated","088691",52)]


def test_tff_and_legacy_have_different_trader_groups():
    base={
        "report_date_as_yyyy_mm_dd":"2026-10-20",
        "cftc_contract_market_code":"13874A",
        "market_and_exchange_names":"E-MINI S&P 500 - CME",
        "open_interest_all":"1000"}
    tff={**base,"dealer_positions_long_all":"100","dealer_positions_short_all":"90",
         "asset_mgr_positions_long":"180","asset_mgr_positions_short":"80",
         "lev_money_positions_long":"220","lev_money_positions_short":"300"}
    data=compute_cot("tff","13874A",[tff])
    assert [p.group for p in data.latest.groups]==["Dealers","Asset Managers","Leveraged Money"]
    legacy={**base,"comm_positions_long_all":"200","comm_positions_short_all":"180",
            "noncomm_positions_long_all":"250","noncomm_positions_short_all":"150"}
    older=compute_cot("legacy","13874A",[legacy])
    assert len(older.latest.groups)==2


def test_wrong_contract_duplicates_and_injection_rejected():
    with pytest.raises(ProviderError,match="different contract"):
        compute_cot("disaggregated","088691",[position("2026-10-20","000000")])
    with pytest.raises(ProviderError,match="Duplicate"):
        compute_cot("disaggregated","088691",[position("2026-10-20"),position("2026-10-20")])
    with pytest.raises(ProviderError,match="invalid"):
        CftcApiSource().history("tff","088691' OR 1=1",52)


def test_cftc_source_sends_encoded_query_and_parses_result():
    requested=[]
    def loader(url):
        requested.append(url)
        if "%24group" in url:
            return json.dumps([market()]).encode()
        return json.dumps([position("2026-10-20")]).encode()
    provider=CftcApiSource(loader)
    assert provider.search("disaggregated","GOLD")[0]["contract_market_name"]=="GOLD"
    assert provider.history("disaggregated","088691",52)[0]["open_interest_all"]=="2000"
    assert all("publicreporting.cftc.gov/resource/72hh-3qpy.json" in url for url in requested)


def test_postgres_adapter_requires_configuration_not_a_database_yet():
    with pytest.raises(ProviderError,match="not configured"):
        PostgresCotSource("")


def test_demo_does_not_fabricate_trader_position_data():
    result=cot_specialist(req(symbol="DEMO"),Services.build("demo"))
    assert result.status=="no_data" and result.cot is None


def test_web_chat_research_includes_structured_cot(monkeypatch):
    import fa_agents.cot as module
    monkeypatch.setattr(module,"get_source",lambda:MockCotSource())
    client=TestClient(app)
    response=client.post("/api/analyze",json={
        "symbol":"NVDA","asset_class":"equity","mode":"live",
        "question":"COT do ouro",
    })
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload["selected_agents"]==["cot"]
    result=payload["report"]["results"][0]
    assert result["agent_id"]=="cot"
    assert result["cot"]["latest"]["report_date"]=="2026-10-20"
    assert "Managed Money" in payload["answer"]


def test_cot_tab_has_picker_and_historical_chart():
    client=TestClient(app)
    js=client.get("/static/app.js").text
    assert "function renderCot(" in js
    assert "cot_market_code" in js
    assert "Net positioning" in js
