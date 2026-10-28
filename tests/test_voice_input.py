"""Offline tests for FA_Agent voice-to-text functionality."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys

import pytest
from fastapi.testclient import TestClient

from fa_agents import voice
from fa_agents.webapp import app


def test_audio_empty_and_invalid_mime():
    with pytest.raises(ValueError, match="Empty"):
        voice.transcribe_audio(b"", "audio/webm")
    with pytest.raises(ValueError, match="Unsupported"):
        voice.transcribe_audio(b"test", "text/plain")


def test_voice_size_limit_without_provider():
    with pytest.raises(ValueError, match="10 MB"):
        voice.transcribe_audio(b"x" * (voice.MAX_AUDIO_BYTES + 1), "audio/webm")


def test_transcription_uses_configured_key_and_does_not_store_bytes(monkeypatch):
    monkeypatch.setenv("FA_VOICE_LANGUAGE", "pt")
    client = Mock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="Como estão os backtests de BTC?")
    openai_ctor = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=openai_ctor))
    with patch("fa_agents.llm.resolve_api_key", return_value="test-credential"):
        text = voice.transcribe_audio(b"sample audio bytes", "audio/webm;codecs=opus")
    assert text == "Como estão os backtests de BTC?"
    assert openai_ctor.call_args.kwargs["api_key"] == "test-credential"
    call = client.audio.transcriptions.create.call_args.kwargs
    assert call["model"] == "gpt-4o-mini-transcribe"
    assert call["file"][0] == "recording.webm"
    assert call["language"] == "pt"


def test_no_hard_coded_language_if_unspecified(monkeypatch):
    monkeypatch.delenv("FA_VOICE_LANGUAGE", raising=False)
    client = Mock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="What's the NVIDIA price?")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Mock(return_value=client)))
    with patch("fa_agents.llm.resolve_api_key", return_value="test"):
        voice.transcribe_audio(b"sample", "audio/mp4")
    assert "language" not in client.audio.transcriptions.create.call_args.kwargs


def test_transcription_endpoint_requires_audio_and_never_calls_analyze():
    client = TestClient(app)
    with patch("fa_agents.webapp.transcribe_audio", return_value="Qual o preço da NVIDIA?") as mock:
        response = client.post("/api/transcribe-audio", files={
            "file": ("voice.webm", b"recorded-data", "audio/webm")
        })
    assert response.status_code == 200
    assert response.json() == {"text": "Qual o preço da NVIDIA?", "requires_review": True}
    mock.assert_called_once_with(b"recorded-data", "audio/webm")


def test_transcription_endpoint_rejects_unsupported_audio():
    client = TestClient(app)
    response = client.post("/api/transcribe-audio", files={
        "file": ("not-audio.txt", b"data", "text/plain")
    })
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_transcription_endpoint_rejects_empty():
    client = TestClient(app)
    response = client.post("/api/transcribe-audio", files={
        "file": ("voice.webm", b"", "audio/webm")
    })
    assert response.status_code == 400


def test_voice_provider_failure_does_not_leak_sensitive_details(monkeypatch):
    client = Mock()
    client.audio.transcriptions.create.side_effect = RuntimeError("SECRET CREDENTIAL leaked in raw exception")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Mock(return_value=client)))
    with patch("fa_agents.llm.resolve_api_key", return_value="test"):
        with pytest.raises(voice.VoiceTranscriptionError) as error:
            voice.transcribe_audio(b"someaudio", "audio/ogg")
    assert "SECRET" not in str(error.value)
