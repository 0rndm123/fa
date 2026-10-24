import pytest
from fa_agents.catalog import choose_agents, SPECIALISTS
from fa_agents.models import ResearchRequest


def test_default_routes():
    assert choose_agents(ResearchRequest(symbol="nvda", asset_class="equity")) == [
        "filings", "fundamental", "news", "technical", "risk"
    ]
    assert "fundamental" not in choose_agents(ResearchRequest(symbol="BTC", asset_class="crypto"))


def test_routing_filters():
    request = ResearchRequest(symbol="BTC", asset_class="crypto",
                              include_agents=["news", "risk", "news"],
                              exclude_agents=["risk"])
    assert choose_agents(request) == ["news"]
    with pytest.raises(ValueError, match="Unknown agent"):
        choose_agents(ResearchRequest(symbol="A", asset_class="equity",
                                     include_agents=["nonexistent"]))
    assert len(SPECIALISTS) == 12
