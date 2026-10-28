"""FA/SysTrd adapter contract tests; no PostgreSQL or running API required."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from fa_agents.catalog import select_for_question
from fa_agents.models import ResearchRequest
from fa_agents.systrd_backtests import SysTrdAPI, backtest_specialist, is_backtest_question


def _request(question="Mostra os meus backtests do BTCUSDT em D"):
    return ResearchRequest(symbol="BTCUSDT", asset_class="crypto", question=question)


def test_backtest_questions_route_to_specialist_for_crypto():
    assert is_backtest_question("Quais os backtests do BTCUSDT?")
    assert select_for_question(_request()) == ["backtest"]


def test_remote_plain_http_is_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        SysTrdAPI("http://public.example.org:8000")


def test_absent_config_does_not_use_postgres(monkeypatch):
    monkeypatch.delenv("FA_SYSTRD_API_URL", raising=False)
    monkeypatch.setenv("SYSTRD_APP_PG_DSN", "postgres://should-not-be-used")
    result = backtest_specialist(_request(), SimpleNamespace(demo=False))
    assert result.status == "no_data"
    assert "not connected" in result.summary


def test_ambiguous_exchange_is_not_combined(monkeypatch):
    monkeypatch.setenv("FA_SYSTRD_API_URL", "http://127.0.0.1:8000")
    monkeypatch.delenv("FA_SYSTRD_CALCULATOR_VERSION", raising=False)
    class Fake:
        def get(self, endpoint, **kw):
            assert endpoint == "scopes"
            return {"items": [
                {"exchange_id": 1, "symbol": "BTCUSDT", "timespan": "D",
                 "calculator_version": "rm-pilot-experimental-v1"},
                {"exchange_id": 2, "symbol": "BTCUSDT", "timespan": "D",
                 "calculator_version": "rm-pilot-experimental-v1"},
            ]}, "http://127.0.0.1/api/v1/backtests/scopes"
    with patch("fa_agents.systrd_backtests.SysTrdAPI", return_value=Fake()):
        result = backtest_specialist(_request(), SimpleNamespace(demo=False))
    assert result.status == "no_data"
    assert "Multiple" in result.summary
    assert len(result.claims) == 2


def test_live_summary_and_trade_observations(monkeypatch):
    monkeypatch.setenv("FA_SYSTRD_API_URL", "http://127.0.0.1:8000")
    class Fake:
        def get(self, endpoint, **filters):
            if endpoint == "scopes":
                return {"items": [{
                    "exchange_id": 3, "symbol": "BTCUSDT", "timespan": "D",
                    "calculator_version": "rm-pilot-experimental-v1",
                }]}, "http://127.0.0.1/api/v1/backtests/scopes"
            assert filters["exchange_id"] == 3
            assert filters["calculator_version"] == "rm-pilot-experimental-v1"
            if endpoint == "summary":
                return {"statistics": {"events": 5, "closed_events": 3,
                           "closed_with_pnl": 3, "winning_trades": 2,
                           "losing_trades": 1, "average_gross_pnl_pct": 1.5,
                           "gross_return_ratio": 2.5},
                        "validation_status": "experimental",
                        "limitations": ["Unverified experimental backtests"]}, "http://127.0.0.1/api/v1/backtests/summary"
            assert endpoint == "operations"
            assert filters["status"] == "CLOSED"
            return {"items": [{"exit_timestamp": "2026-10-20T12:00:00",
                               "pnl_pct": 2.3}]}, "http://127.0.0.1/api/v1/backtests/operations"
    with patch("fa_agents.systrd_backtests.SysTrdAPI", return_value=Fake()):
        result = backtest_specialist(_request(), SimpleNamespace(demo=False))
    assert result.status == "partial"
    assert result.metrics["closed_events"] == 3
    assert result.metrics["gross_return_ratio"] == 2.5
    assert result.observations[0].value == 2.3
    assert result.evidence[0].source_name.startswith("SysTrd")


def test_demo_cannot_read_live_sys_trd(monkeypatch):
    monkeypatch.setenv("FA_SYSTRD_API_URL", "http://127.0.0.1:8000")
    result = backtest_specialist(_request(), SimpleNamespace(demo=True))
    assert result.status == "no_data"
