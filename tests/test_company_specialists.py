"""Offline tests for specialist routing, source integrity and OHLC market candles."""
import json
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from fa_agents.agents import Services, technical
from fa_agents.catalog import select_for_question
from fa_agents.company_specialists import (
    performance, debt_liquidity, governance, industry_context, competition,
)
from fa_agents.market_data import YahooQuoteAgent, BinanceSpotQuoteAgent
from fa_agents.models import ResearchRequest
from fa_agents.providers import DemoSEC, DemoNews, now
from fa_agents.webapp import app


def req(question="Evaluate NVIDIA"):
    return ResearchRequest(symbol="DEMO",asset_class="equity",question=question)


def demo():
    return Services(sec=DemoSEC(),news=DemoNews(),demo=True)


@pytest.mark.parametrize("text,needed", [
    ("Qual a dívida e liquidez da NVIDIA?",{"debt_liquidity","financial_data"}),
    ("Como evoluíram receitas e margens?",{"financial_performance","fundamental"}),
    ("Analisa a governance da empresa",{"governance"}),
    ("Quais os concorrentes e o setor?",{"competition","industry_context"}),
    ("Qual é o RSI e tendência da NVIDIA?",{"technical"}),
])
def test_natural_language_routes_to_relevant_specialists(text,needed):
    selected=select_for_question(req(text))
    assert needed.issubset(selected)


def test_manual_specialists_override_intent():
    request=req("Quais são os concorrentes?")
    request.include_agents=["financial_data"]
    assert select_for_question(request)==["financial_data"]


def test_company_performance_uses_filed_financial_facts():
    result=performance(req(),demo())
    assert result.status=="completed"
    assert result.metrics["revenue_yoy_pct"]==15.0
    assert result.metrics["fcf_proxy_usd"]==120_000
    assert all(e.is_synthetic for e in result.evidence)
    assert len(result.observations)>=6


def test_debt_agent_does_not_invent_metrics_when_balance_facts_are_missing():
    result=debt_liquidity(req(),demo())
    assert result.status=="no_data"
    assert "cash_usd" not in result.metrics


def test_debt_agent_computes_current_ratio_without_double_counting_debt():
    class ExtendedDemo(DemoSEC):
        def facts(self, issuer):
            payload=super().facts(issuer)
            data=payload["facts"]["us-gaap"]
            values={
                "AssetsCurrent":300,
                "LiabilitiesCurrent":150,
                "LongTermDebtNoncurrent":80,
                "LongTermDebtCurrent":20,
                "CashAndCashEquivalentsAtCarryingValue":50,
            }
            for k,v in values.items():
                data[k]={"units":{"USD":[{
                    "end":"2024-12-31","filed":"2025-02-10",
                    "form":"10-K","fp":"FY","val":v
                }]}}
            return payload
    service=Services(sec=ExtendedDemo(),news=DemoNews(),demo=True)
    result=debt_liquidity(req(),service)
    assert result.status=="partial"
    assert result.metrics["current_ratio"]==2
    assert result.metrics["reported_debt_components_usd"]==100
    assert result.metrics["working_capital_usd"]==150
    assert result.metrics["noncurrent_debt_less_cash_usd"]==30


def test_governance_is_document_discovery_not_an_unearned_assessment():
    result=governance(req(),demo())
    assert result.status=="partial"
    assert len(result.evidence)>=1
    assert not result.metrics
    assert any("not been evaluated" in x for x in result.limitations)


def test_sector_sic_and_competition_without_unverified_peer_claims():
    sector=industry_context(req(),demo())
    assert sector.status=="partial"
    assert sector.metrics["sic"]=="7372"
    peers=competition(req(),demo())
    assert peers.status=="partial"
    assert not peers.metrics
    assert any("Not a competitor ranking" in x for x in peers.limitations)


def test_yahoo_ohlc_bars_are_real_provider_data_not_inferred_close():
    t=int(now().timestamp())-600
    fake={
        "chart":{"error":None,"result":[{
            "meta":{"symbol":"NVDA","regularMarketPrice":110,
                    "regularMarketTime":t,"currency":"USD"},
            "timestamp":[t-3600,t],
            "indicators":{"quote":[{
                "open":[99,106],"high":[108,112],"low":[98,103],"close":[105,110],
            }]},
        }]}
    }
    q=YahooQuoteAgent(loader=lambda url:json.dumps(fake).encode()).fetch("NVDA")
    assert len(q.bars)==2
    assert q.bars[0].open==99 and q.bars[-1].high==112
    assert q.bar_interval=="1h"


def test_binance_candles_use_separate_public_klines_endpoint():
    t=int(now().timestamp())-500
    def fake(url):
        if "/klines" in url:
            return json.dumps([
                [t*1000-3600_000,"101","103","100","102","55"],
                [t*1000,"102","104","101","103","70"],
            ]).encode()
        return json.dumps({
            "symbol":"BTCUSDT","lastPrice":"103",
            "closeTime":t*1000,"prevClosePrice":"100"
        }).encode()
    q=BinanceSpotQuoteAgent(loader=fake).fetch("BTCUSDT")
    assert len(q.bars)==2
    assert len(q.history)==2
    assert q.bars[-1].close==103


def test_live_technical_agent_works_without_csv_using_market_provider(monkeypatch):
    from fa_agents import market_data
    t=now()-timedelta(hours=60)
    from fa_agents.models import MarketQuote,PricePoint,QuoteResult,ProviderAttempt
    history=[PricePoint(at=t+timedelta(hours=i),price=100+i*.1) for i in range(60)]
    quote=MarketQuote(provider="yahoo",symbol="NVDA",instrument="NVDA",venue="NASDAQ",
          currency="USD",price=105.9,at=history[-1].at,retrieved_at=now(),
          timestamp_kind="regular_market_quote",source_url="https://finance.yahoo.com/quote/NVDA/",
          caveat="Unofficial vendor",history=history,bar_interval="1h")
    class Fake:
        def get_quote(self,symbol,asset_class):
            assert symbol=="NVDA"
            return QuoteResult(requested_symbol=symbol,asset_class=asset_class,selected=quote)
    monkeypatch.setattr(market_data,"MarketDataOrchestrator",Fake)
    request=ResearchRequest(symbol="NVDA",asset_class="equity",question="Qual é o RSI?")
    result=technical(request,Services.build())
    assert result.status=="partial"
    assert result.metrics["timeframe"]=="1h"
    assert "sma20_1h" in result.metrics and "rsi14_simple" in result.metrics
    assert "sma200" not in result.metrics


def test_web_demo_question_routes_and_remains_source_limited():
    client=TestClient(app)
    result=client.post("/api/analyze",json={
        "symbol":"DEMO","mode":"demo","question":"Qual a governance da empresa?",
    })
    assert result.status_code==200,result.text
    data=result.json()
    assert data["selected_agents"]==["governance"]
    assert data["report"]["results"][0]["status"]=="partial"


def test_interactive_chart_frontend_loaded():
    client=TestClient(app)
    html=client.get("/").text
    script=client.get("/static/interactive_chart.js")
    appjs=client.get("/static/app.js")
    assert 'interactive_chart.js' in html
    assert script.status_code==200
    assert "createInteractiveChart" in script.text
    assert "Candles" in script.text
    assert "pointermove" in script.text
    assert "renderSpecialistTopic" in appjs.text
