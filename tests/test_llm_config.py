"""Test environment variable fallback without contacting OpenAI."""
import pytest
from fa_agents.llm import resolve_api_key


def test_uses_existing_demo_alias(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY_Demo", "test-fallback-placeholder")
    assert resolve_api_key() == "test-fallback-placeholder"


def test_conventional_key_has_priority(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-conventional-placeholder")
    monkeypatch.setenv("OPENAI_API_KEY_Demo", "test-fallback-placeholder")
    assert resolve_api_key() == "test-conventional-placeholder"


def test_missing_both_keys_is_reported(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_Demo", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY_Demo"):
        resolve_api_key()
