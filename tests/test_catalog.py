import pytest

from fa_agents.catalog import SPECIALISTS, choose_agents
from fa_agents.models import ResearchRequest


def test_equity_selects_core_specialists():
    result = choose_agents(ResearchRequest(symbol="nvda", asset_class="equity"))
    assert result[0] == "filings"
    assert "fundamental" in result
    assert "risk" in result


def test_crypto_does_not_run_equity_valuation():
    result = choose_agents(ResearchRequest(symbol="btc", asset_class="crypto"))
    assert "crypto_onchain" in result
    assert "valuation" not in result


def test_include_exclude_and_deduplicate():
    request = ResearchRequest(
        symbol="gold",
        asset_class="commodity",
        include_agents=["news", "macro", "news"],
        exclude_agents=["macro"],
    )
    assert choose_agents(request) == ["news"]


def test_unknown_agent_rejected():
    with pytest.raises(ValueError, match="Unknown agent"):
        choose_agents(ResearchRequest(symbol="ABC", asset_class="equity", include_agents=["fake"]))


def test_contracts_do_not_assume_functional_agents():
    assert len(SPECIALISTS) >= 10
    assert ResearchRequest(symbol=" btc ", asset_class="crypto").symbol == "BTC"
