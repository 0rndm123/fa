"""Offline tests for opt-in spoken FA replies, no external API calls."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys

import pytest
from fastapi.testclient import TestClient

from fa_agents import voice
from fa_agents.webapp import app


def test_spoken_reply_limits_before_provider():
    with pytest.raises(ValueError, match="non-empty"):
        voice.synthesize_speech("")
    with pytest.raises(ValueError, match="2200"):
        voice.synthesize_speech("a" * (voice.MAX_SPEECH_CHARS + 1))


def test_tts_calls_explicit_provider_and_does_not_save_audio(monkeypatch):
    monkeypatch.delenv("FA_VOICE_NAME", raising=False)
    openai = Mock()
    openai.audio.speech.create.return_value = SimpleNamespace(content=b"valid mp3 bytes")
    constructor = Mock(return_value=openai)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    with patch("fa_agents.llm.resolve_api_key", return_value="testing-only"):
        data = voice.synthesize_speech("Analise a NVIDIA.")
    assert data == b"valid mp3 bytes"
    assert constructor.call_args.kwargs["api_key"] == "testing-only"
    kwargs = openai.audio.speech.create.call_args.kwargs
    assert kwargs == {
        "model": "gpt-4o-mini-tts",
        "voice": "cedar",
        "input": "Analise a NVIDIA.",
        "response_format": "mp3",
        "instructions": kwargs["instructions"],
    }
    assert "European Portuguese" in kwargs["instructions"]
    assert "British English" in kwargs["instructions"]


def test_unsupported_voice_does_not_call_provider(monkeypatch):
    monkeypatch.setenv("FA_VOICE_NAME", "invalid")
    constructor = Mock()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    with patch("fa_agents.llm.resolve_api_key", return_value="testing-only"):
        with pytest.raises(ValueError, match="FA_VOICE_NAME"):
            voice.synthesize_speech("Olá.")
    constructor.assert_not_called()


def test_provider_failure_redacts_sensitive_errors(monkeypatch):
    monkeypatch.delenv("FA_VOICE_NAME", raising=False)
    openai = Mock()
    openai.audio.speech.create.side_effect = RuntimeError("SECRET API KEY in HTTP error")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Mock(return_value=openai)))
    with patch("fa_agents.llm.resolve_api_key", return_value="testing-only"):
        with pytest.raises(voice.VoiceTranscriptionError) as err:
            voice.synthesize_speech("Um resumo.")
    assert "SECRET" not in str(err.value)


def test_spoken_endpoint_only_plays_text_and_sets_no_store():
    client = TestClient(app)
    with patch("fa_agents.webapp.synthesize_speech", return_value=b"audio mp3") as speak:
        result = client.post("/api/speak-reply", json={"text": "Test answer"})
    assert result.status_code == 200
    assert result.content == b"audio mp3"
    assert result.headers["content-type"].startswith("audio/mpeg")
    assert result.headers["cache-control"] == "no-store"
    speak.assert_called_once_with("Test answer")


def test_spoken_endpoint_rejects_oversized_text():
    result = TestClient(app).post("/api/speak-reply", json={"text": "a" * 2201})
    assert result.status_code == 422


def test_spoken_endpoint_handles_provider_failure():
    with patch("fa_agents.webapp.synthesize_speech",
               side_effect=voice.VoiceTranscriptionError("Voice unavailable")):
        response = TestClient(app).post("/api/speak-reply", json={"text": "Test"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Voice unavailable"


def test_ui_speech_controls_are_opt_in():
    from pathlib import Path
    web = Path(__file__).resolve().parents[1] / "src" / "fa_agents" / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    assert 'id="autoSpeak" disabled' in html
    assert 'id="speakReply"' in html
    assert 'if($("autoSpeak").checked&&!window.FAVoiceDialogue?.active())void speakLatestAnswer()' in js
    assert 'scope:conversationScope()' in js
    assert 'filter(x=>x.scope===conversationScope())' in js
    assert '"/api/speak-reply"' in js
