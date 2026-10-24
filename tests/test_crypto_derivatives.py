"""Offline tests for BTC/ETH COT and Binance crypto derivatives."""
import json
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from fa_agents.agents import Services
from fa_agents.catalog import select_for_question
from fa_agents.cot import select_cot_market
from fa_agents.crypto_derivatives import (
    BinanceUsdmSource, is_derivatives_question, research_crypto_derivatives,
    resolve_pair, crypto_answer,
)
from fa_agents.models import ResearchRequest
from fa_agents.providers import ProviderError, now
from fa_agents.webapp import app


def request(symbol="BTC",question="Qual é o funding do Bitcoin?"):
    return ResearchRequest(symbol=symbol,asset_class="crypto",question=question)


def ms(hours=0):
    return int((now()-timedelta(hours=hours)).timestamp()*1000)


def test_crypto_cot_maps_to_futures_market_search():
    assert select_cot_market("COT Bitcoin","BTC")==("tff","BITCOIN")
    assert select_cot_market("COT BTC","BTC")==("tff","BITCOIN")
    assert select_cot_market("COT Ether","ETH")==("tff","ETHER")
    assert select_cot_market("COT Ethereum","ETH")==("tff","ETHER")
    assert select_cot_market("COT","BTC")==("tff","BITCOIN")
    assert select_for_question(request("BTC","Qual o COT do BTC?"))==["cot"]
    assert select_for_question(request("ETH","Mostra o COT do Ether"))==["cot"]
    assert select_cot_market("COT da NVIDIA","BTC")==("tff",None)


def test_derivative_routing_without_confusing_cot_or_spot():
    assert is_derivatives_question("Qual é o funding do BTC?")
    assert is_derivatives_question("Open interest BTC")
    assert is_derivatives_question("Rácio long/short do Ethereum")
    assert not is_derivatives_question("COT do bitcoin")
    assert not is_derivatives_question("Qual o preço da NVIDIA?")
    assert select_for_question(request("BTC","Open interest BTC"))==["crypto_derivatives"]
    assert select_for_question(request("ETH","Quanto está o funding do ETH?"))==["crypto_derivatives"]


@pytest.mark.parametrize(("ticker","pair"),[
    ("BTC","BTCUSDT"),("BTC-USD","BTCUSDT"),("BTCUSDT","BTCUSDT"),
    ("ETH","ETHUSDT"),("SOL","SOLUSDT")])
def test_contract_mapping(ticker,pair):
    assert resolve_pair(ticker)==pair


def test_unverified_contracts_rejected():
    with pytest.raises(ProviderError,match="not available"):
        resolve_pair("NVDA")
    with pytest.raises(ProviderError,match="not available"):
        resolve_pair("UNKNOWNCOIN")


def mock_payload(url):
    if "/fundingRate" in url:
        return json.dumps([
            {"symbol":"BTCUSDT","fundingRate":"-0.00014","fundingTime":ms(hours=16)},
            {"symbol":"BTCUSDT","fundingRate":"0.00010","fundingTime":ms(hours=8)},
        ]).encode()
    if "/openInterest" in url:
        return json.dumps({"symbol":"BTCUSDT","openInterest":"12345.75",
                           "time":ms(hours=1)}).encode()
    if "/globalLongShortAccountRatio" in url:
        return json.dumps([
            {"symbol":"BTCUSDT","longShortRatio":"1.15","timestamp":ms(hours=24)},
            {"symbol":"BTCUSDT","longShortRatio":"1.20","timestamp":ms(hours=1)},
        ]).encode()
    raise AssertionError("Unexpected endpoint "+url)


def test_binance_public_data_and_negative_funding():
    provider=BinanceUsdmSource(loader=mock_payload)
    result=research_crypto_derivatives(request(),Services.build(),source=provider)
    assert result.status=="completed"
    assert result.metrics["funding_rate_pct"]==0.01
    assert result.metrics["open_interest"]==12345.75
    assert result.metrics["global_long_short_account_ratio"]==1.2
    assert result.crypto_derivatives is not None
    series=result.crypto_derivatives.series
    negative=next(p for p in series if p.metric=="funding_rate_pct" and p.value<0)
    assert negative.value==-0.014
    assert result.crypto_derivatives.instrument=="BTCUSDT"
    assert len(result.evidence)==3
    assert "Binance USD-M" in crypto_answer(result)


def test_partial_outage_does_not_invent_missing_metrics():
    def loader(url):
        if "/fundingRate" in url:
            return json.dumps([{"symbol":"BTCUSDT","fundingRate":"0.0001",
                                "fundingTime":ms(hours=8)}]).encode()
        raise ProviderError("offline")
    result=research_crypto_derivatives(
        request(),Services.build(),source=BinanceUsdmSource(loader=loader))
    assert result.status=="partial"
    assert result.metrics["funding_rate_pct"]==0.01
    assert "open_interest" not in result.metrics
    assert any("Open interest" in x for x in result.limitations)


def test_mismatched_provider_pair_never_becomes_a_value():
    def loader(url):
        if "/openInterest" in url:
            return json.dumps({"symbol":"ETHUSDT","openInterest":"123",
                               "time":ms(hours=1)}).encode()
        if "/fundingRate" in url:
            return json.dumps([{"symbol":"ETHUSDT","fundingRate":"0.0001",
                                "fundingTime":ms(hours=1)}]).encode()
        return json.dumps([{"symbol":"ETHUSDT","longShortRatio":"1.2",
                            "timestamp":ms(hours=1)}]).encode()
    result=research_crypto_derivatives(
        request(),Services.build(),source=BinanceUsdmSource(loader=loader))
    assert result.status=="no_data" and result.crypto_derivatives is None
    assert any("wrong pair" in x.lower() or "mismatch" in x.lower()
               for x in result.limitations)


def test_demo_and_equity_do_not_return_exchange_positions():
    assert research_crypto_derivatives(request(),Services.build("demo")).status=="no_data"
    equity=ResearchRequest(symbol="NVDA",asset_class="equity",question="Funding")
    assert research_crypto_derivatives(equity,Services.build()).status=="no_data"


def test_web_chat_routes_crypto_derivatives(monkeypatch):
    import fa_agents.crypto_derivatives as module
    monkeypatch.setattr(module,"BinanceUsdmSource",
                        lambda:BinanceUsdmSource(loader=mock_payload))
    client=TestClient(app)
    response=client.post("/api/analyze",json={
        "symbol":"BTC","asset_class":"crypto","mode":"live",
        "question":"Como está o funding e open interest do BTC?"})
    assert response.status_code==200,response.text
    body=response.json()
    assert body["selected_agents"]==["crypto_derivatives"]
    agent=body["report"]["results"][0]
    assert agent["status"]=="completed"
    assert agent["crypto_derivatives"]["instrument"]=="BTCUSDT"
    assert "Funding liquidado" in body["answer"]


def test_crypto_tab_frontend_available():
    client=TestClient(app)
    js=client.get("/static/app.js")
    assert js.status_code==200
    assert "Crypto Derivatives" in js.text
    assert "function renderCryptoDerivatives(" in js.text
    assert "Historical Binance Futures observations" in js.text
