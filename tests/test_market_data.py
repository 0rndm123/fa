"""Market-data crew: deterministic offline provider tests; no external requests."""
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient

from fa_agents.market_data import (
    BinanceSpotQuoteAgent, YahooQuoteAgent, TradingViewQuoteAgent,
    MarketDataOrchestrator, extract_symbol, is_price_question, quote_answer,
)
from fa_agents.models import QuoteResult
from fa_agents.providers import ProviderError, now
from fa_agents.webapp import app


def unix():
    return int(now().timestamp()) - 180


def yahoo_fixture(symbol="NVDA", price=123.45):
    t = unix()
    return json.dumps({"chart": {"error": None, "result": [{
        "meta": {"symbol":symbol, "regularMarketPrice":price,
                 "regularMarketTime":t, "currency":"USD",
                 "exchangeName":"NMS", "shortName":"NVIDIA Corporation",
                 "chartPreviousClose":120.0},
        "timestamp":[t-3600,t],
        "indicators":{"quote":[{"close":[120.0,price]}]},
    }]}}).encode()


def binance_fixture(symbol="BTCUSDT", price="68000.12"):
    return json.dumps({"symbol":symbol,"lastPrice":price,
                       "closeTime":unix()*1000, "prevClosePrice":"67000.00"}).encode()


def test_price_question_detection_and_company_aliases():
    assert is_price_question("Qual é o preço da NVIDIA?")
    assert is_price_question("What is the current stock price of Apple?")
    assert not is_price_question("Qual é o preço justo da NVIDIA?")
    assert not is_price_question("Analisa a evolução do preço da NVIDIA")
    assert extract_symbol("Qual é o preço da NVIDIA?", "DEMO", "equity") == ("NVDA", "equity")
    assert extract_symbol("Qual o preço do Bitcoin?", "NVDA", "equity") == ("BTC","crypto")
    assert extract_symbol("Qual o preço de TSLA?", "NVDA", "equity") == ("TSLA","equity")
    assert extract_symbol("Qual o preço agora?", "NVDA", "equity") == ("NVDA","equity")


def test_yahoo_subagent_returns_timed_quote_and_history():
    q=YahooQuoteAgent(loader=lambda url:yahoo_fixture()).fetch("NVDA")
    assert q.provider=="yahoo"
    assert q.currency=="USD" and q.price==123.45
    assert q.symbol=="NVDA" and len(q.history)==2
    assert q.at.tzinfo is not None
    assert "unofficial" in q.caveat.lower()


def test_yahoo_does_not_accept_different_instrument():
    try:
        YahooQuoteAgent(loader=lambda url:yahoo_fixture("AAPL")).fetch("NVDA")
        assert False,"Expected failure"
    except ProviderError as exc:
        assert "Wrong" in str(exc)


def test_binance_official_spot_agent_and_quote_currency():
    q=BinanceSpotQuoteAgent(loader=lambda url:binance_fixture()).fetch("BTCUSDT")
    assert q.provider=="binance" and q.symbol=="BTCUSDT"
    assert q.price==68000.12 and q.currency=="USDT"
    assert q.timestamp_kind=="rolling_24h_window_end"


def test_binance_rejects_invalid_price_and_wrong_symbol():
    data=json.loads(binance_fixture())
    data["lastPrice"]="0"
    bad=BinanceSpotQuoteAgent(loader=lambda url:json.dumps(data).encode())
    try:
        bad.fetch("BTCUSDT")
        assert False,"Expected price rejection"
    except ProviderError:
        pass


def test_tradingview_requires_explicit_authorized_local_adapter():
    agent=TradingViewQuoteAgent(adapter_url="")
    try:
        agent.fetch("NASDAQ:NVDA")
        assert False,"No adapter should fail"
    except ProviderError as exc:
        assert "not configured" in str(exc)
    bad=TradingViewQuoteAgent(adapter_url="https://evil.example/quote")
    try:
        bad.fetch("NASDAQ:NVDA")
        assert False,"Non-local adapter should fail"
    except ProviderError as exc:
        assert "localhost" in str(exc)


def test_market_orchestrator_chooses_yahoo_for_equity():
    dispatcher=MarketDataOrchestrator(
        yahoo=YahooQuoteAgent(loader=lambda url:yahoo_fixture()),
        binance=BinanceSpotQuoteAgent(loader=lambda url:binance_fixture()),
        tradingview=TradingViewQuoteAgent(adapter_url=""),
    )
    result=dispatcher.get_quote("NVDA","equity")
    assert result.selected.provider=="yahoo"
    assert [a.provider for a in result.attempts]==["yahoo"]
    assert "NVDA" in quote_answer(result)


def test_market_orchestrator_prioritizes_binance_for_crypto_no_mixing():
    def yahoo_bitcoin(url):
        return yahoo_fixture(symbol="BTC-USD",price=68100.0)
    dispatcher=MarketDataOrchestrator(
        yahoo=YahooQuoteAgent(loader=yahoo_bitcoin),
        binance=BinanceSpotQuoteAgent(loader=lambda url:binance_fixture()),
        tradingview=TradingViewQuoteAgent(adapter_url=""),
    )
    result=dispatcher.get_quote("BTC","crypto")
    assert result.selected.provider=="binance"
    assert result.selected.currency=="USDT"
    assert len(result.attempts)==2
    assert result.attempts[1].quote.currency=="USD"
    assert "Outras fontes" in quote_answer(result)


def test_provider_outage_is_explicit_and_falls_back():
    def offline(url):
        raise ProviderError("rate limited")
    dispatcher=MarketDataOrchestrator(
        yahoo=YahooQuoteAgent(loader=offline),
        binance=BinanceSpotQuoteAgent(loader=lambda url:binance_fixture()),
        tradingview=TradingViewQuoteAgent(adapter_url=""),
    )
    result=dispatcher.get_quote("BTC","crypto")
    assert result.selected.provider=="binance"
    assert result.attempts[1].status=="failed"
    assert "rate limited" in result.attempts[1].error


def test_workbench_answers_price_question_without_full_research(monkeypatch):
    import fa_agents.webapp as web
    quote=YahooQuoteAgent(loader=lambda url:yahoo_fixture()).fetch("NVDA")
    data=QuoteResult(requested_symbol="NVDA",asset_class="equity",
                     selected=quote,attempts=[
                         {"provider":"yahoo","status":"ok","symbol":"NVDA",
                          "quote":quote.model_dump(mode="json")}
                     ])
    class Fake:
        def get_quote(self,symbol,asset_class):
            assert (symbol,asset_class)==("NVDA","equity")
            return data
    monkeypatch.setattr(web,"MarketDataOrchestrator",lambda:Fake())
    client=TestClient(app)
    response=client.post("/api/analyze",json={
        "symbol":"DEMO","mode":"live","asset_class":"equity",
        "question":"Qual é o preço da NVIDIA?",
    })
    assert response.status_code==200,response.text
    body=response.json()
    assert "123,4500 USD" in body["answer"]
    assert body["report"]["market_quote"]["selected"]["provider"]=="yahoo"
    assert body["selected_agents"]==["quote_yahoo"]
    assert body["report"]["results"][0]["agent_id"]=="quote_yahoo"


def test_demo_does_not_silently_fetch_real_quote():
    client=TestClient(app)
    r=client.post("/api/analyze",json={
        "symbol":"DEMO","mode":"demo","asset_class":"equity",
        "question":"Qual é o preço da NVIDIA?",
    })
    assert r.status_code==400
    assert "Live" in r.json()["detail"]
