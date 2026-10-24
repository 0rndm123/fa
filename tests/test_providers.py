from datetime import datetime
import pytest

from fa_agents.providers import SEC, ProviderError, annual, prices_from_csv, DemoSEC
from fa_agents.agents import Services, technical
from fa_agents.models import ResearchRequest


def test_sec_requires_real_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with pytest.raises(ProviderError, match="SEC_USER_AGENT"):
        SEC()


def test_sec_resolution_and_annual_values_with_mock_loader():
    calls = []
    def loader(url):
        calls.append(url)
        return b'{"0":{"ticker":"NVDA","cik_str":1045810,"title":"NVIDIA"}}'
    provider = SEC(loader=loader)
    issuer = provider.resolve("NVDA")
    assert issuer.cik10 == "0001045810"
    assert provider.resolve("NVDA") == issuer
    assert len(calls) == 1


def test_prevent_lookahead_in_annual_companyfacts():
    facts = DemoSEC().facts(DemoSEC().resolve("DEMO"))
    old = annual(facts, ("Revenues",), datetime(2024, 12, 31))
    recent = annual(facts, ("Revenues",), datetime(2025, 3, 1))
    assert len(old) == 1 and old[0]["value"] == 1000000
    assert len(recent) == 2 and recent[0]["value"] == 1150000


def test_prices_csv_and_technical_smas(tmp_path):
    csv_path = tmp_path / "prices.csv"
    lines = ["date,close"] + [
        f"2026-01-{day:02d},{day + 100}" for day in range(1, 31)
    ]
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    prices = prices_from_csv(str(csv_path))
    assert len(prices) == 30
    req = ResearchRequest(symbol="TEST", asset_class="equity")
    result = technical(req, Services(prices_csv=str(csv_path)))
    assert result.status == "partial"
    assert result.metrics["sma20"] == 120.5
    assert "sma50" not in result.metrics


def test_duplicate_prices_rejected(tmp_path):
    path = tmp_path / "duplicates.csv"
    path.write_text("date,close\n2025-01-01,10\n2025-01-01,12\n")
    with pytest.raises(ProviderError, match="Duplicate"):
        prices_from_csv(str(path))
