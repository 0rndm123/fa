"""SEC user-agent lookup must work when Windows User env was set after launch.

No contacts, secrets or external SEC calls appear in these tests.
"""
import pytest
from fastapi.testclient import TestClient

from fa_agents import providers
from fa_agents.webapp import app


def test_windows_user_setting_fallback_when_process_has_no_variable(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(providers, "_windows_user_sec_agent",
                        lambda: "FA_Agent contact@example.org")
    identity, source = providers.sec_user_agent_config()
    assert source == "windows_user"
    assert identity == "FA_Agent contact@example.org"
    assert providers.SEC().ua == identity


def test_process_variable_prioritized_over_saved_user_setting(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "FA_Agent process@example.org")
    monkeypatch.setattr(providers, "_windows_user_sec_agent",
                        lambda: "FA_Agent saved@example.org")
    identity, source = providers.sec_user_agent_config()
    assert source == "process"
    assert identity == "FA_Agent process@example.org"
    assert providers.SEC().ua == identity


def test_invalid_process_env_falls_back_to_valid_saved_env(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "FA_Agent without an email")
    monkeypatch.setattr(providers, "_windows_user_sec_agent",
                        lambda: "FA_Agent valid@example.org")
    identity, source = providers.sec_user_agent_config()
    assert source == "windows_user"
    assert identity == "FA_Agent valid@example.org"


def test_missing_or_invalid_identity_is_explicit_without_web_request(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(providers, "_windows_user_sec_agent", lambda: "")
    assert providers.sec_user_agent_config() == ("", "missing")
    with pytest.raises(providers.ProviderError, match="SEC_USER_AGENT not configured"):
        providers.SEC()


def test_explicit_user_agent_does_not_depend_on_platform_settings(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(providers, "_windows_user_sec_agent", lambda: "")
    assert providers.SEC(user_agent="ResearchBot support@example.org").ua == (
        "ResearchBot support@example.org")


def test_api_capabilities_reports_readiness_without_exposing_email(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.setattr(providers, "_windows_user_sec_agent",
                        lambda: "FA_Agent private@example.org")
    response=TestClient(app).get("/api/capabilities")
    assert response.status_code == 200
    body=response.json()
    assert body["sec_configured"] is True
    assert body["sec_config_source"] == "windows_user"
    assert "private@example.org" not in response.text


def test_windows_start_script_checks_readiness_without_echoing_identification():
    from pathlib import Path
    contents=(Path(__file__).parents[1] / "START_FA.bat").read_text(encoding="utf-8")
    assert "GetEnvironmentVariable('SEC_USER_AGENT','User')" in contents
    assert "from fa_agents.providers import sec_user_agent_config" in contents
    assert "echo %SEC_USER_AGENT%" not in contents
