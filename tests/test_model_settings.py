"""Offline tests for model settings and voice model routing."""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from fa_agents import model_settings, voice
from fa_agents.webapp import app


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("FA_MODEL_SETTINGS_FILE", str(tmp_path / "models.json"))
    monkeypatch.delenv("FA_VOICE_LANGUAGE", raising=False)
    return tmp_path


def test_defaults_and_per_agent_model_persist(isolated):
    original = model_settings.load_settings()
    assert original["agent_ai_enabled"] == []
    assert original["voice"] == "cedar"
    original["synthesis"] = "gpt-4o-mini"
    original["speech"] = "tts-1"
    original["transcription"] = "gpt-4o-transcribe"
    original["agent_models"]["fundamental"] = "gpt-4.1"
    original["agent_ai_enabled"] = ["fundamental"]
    returned = model_settings.save_settings(original)
    assert returned == model_settings.load_settings()
    assert model_settings.settings_path().is_file()
    assert "api_key" not in model_settings.settings_path().read_text()


def test_unknown_agent_and_fields_rejected(isolated):
    with pytest.raises(ValueError, match="Unknown agent"):
        model_settings.save_settings({"agent_models": {"arbitrary_agent": "gpt-4.1"}})
    with pytest.raises(ValueError, match="Unknown model settings"):
        model_settings.save_settings({"openai_api_key": "secret"})
    with pytest.raises(ValueError, match="Invalid model"):
        model_settings.save_settings({"speech": "../invalid"})


def test_put_and_get_settings(isolated):
    client = TestClient(app)
    initial = client.get("/api/model-settings")
    assert initial.status_code == 200
    config = initial.json()["settings"]
    catalog = initial.json()["catalog"]
    assert catalog["agents"]
    config["agent_models"] = {"news": "gpt-4.1"}
    config["agent_ai_enabled"] = ["news"]
    response = client.put("/api/model-settings", json=config)
    assert response.status_code == 200
    assert client.get("/api/model-settings").json()["settings"]["agent_models"]["news"] == "gpt-4.1"


def test_oversized_settings_rejected(isolated):
    response = TestClient(app).put("/api/model-settings",
        data=b"x"*33000, headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_voice_transcription_uses_selected_model(isolated, monkeypatch):
    config = model_settings.load_settings()
    config["transcription"] = "gpt-4o-transcribe"
    config["language"] = "pt"
    model_settings.save_settings(config)
    client = Mock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="Ouro no COT")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Mock(return_value=client)))
    with patch("fa_agents.llm.resolve_api_key", return_value="test"):
        answer = voice.transcribe_audio(b"audio", "audio/webm")
    assert answer == "Ouro no COT"
    options = client.audio.transcriptions.create.call_args.kwargs
    assert options["model"] == "gpt-4o-transcribe"
    assert options["language"] == "pt"


def test_voice_tts_uses_configured_model_and_voice(isolated, monkeypatch):
    config = model_settings.load_settings()
    config["speech"] = "tts-1"
    config["voice"] = "nova"
    model_settings.save_settings(config)
    client = Mock()
    client.audio.speech.create.return_value.read.return_value = b"sample.mp3"
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Mock(return_value=client)))
    with patch("fa_agents.llm.resolve_api_key", return_value="test"):
        audio = voice.synthesize_speech("Boa tarde.")
    assert audio == b"sample.mp3"
    options = client.audio.speech.create.call_args.kwargs
    assert options["model"] == "tts-1"
    assert options["voice"] == "nova"
    assert "instructions" not in options


def test_speak_endpoint_returns_audio_without_persisting_it(isolated):
    client = TestClient(app)
    with patch("fa_agents.webapp.synthesize_speech", return_value=b"mp3-data") as model:
        response = client.post("/api/voice/speak", json={"text":"O BTC recuperou."})
    assert response.status_code == 200
    assert response.content == b"mp3-data"
    assert response.headers["content-type"] == "audio/mpeg"
    model.assert_called_once_with("O BTC recuperou.")


def test_audio_transcribe_api_compatibility(isolated):
    client = TestClient(app)
    with patch("fa_agents.webapp.transcribe_audio", return_value="Qual o preço do BTC?") as provider:
        response = client.post("/api/voice/transcribe", data=b"audio",
            headers={"Content-Type":"audio/webm"})
    assert response.status_code == 200
    assert response.json()["requires_review"] is True
    provider.assert_called_once_with(b"audio","audio/webm")


def test_bad_model_settings_file_fails_closed(isolated):
    file=model_settings.settings_path()
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_text(json.dumps({"speech": "../invalid"}),encoding="utf-8")
    with pytest.raises(ValueError,match="unreadable or invalid"):
        model_settings.load_settings()
