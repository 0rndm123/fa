"""Offline voice integration tests. No external audio calls or charged API use."""
from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from fa_agents.voice import transcribe_audio, synthesize_speech, VoiceError, MAX_AUDIO_BYTES
from fa_agents.webapp import app

client = TestClient(app)


def test_voice_controls_present_but_opt_in():
    page = client.get("/")
    assert page.status_code == 200
    for item in ("voiceMic", "voiceStop", "voiceAuto", "voiceStatus"):
        assert 'id="' + item + '"' in page.text
    assert client.get("/static/voice-ui.js").status_code == 200


def test_invalid_audio_type_and_size_fail_before_network():
    unsupported = client.post("/api/voice/transcribe", data=b"fake", headers={"content-type": "application/octet-stream"})
    assert unsupported.status_code == 415
    missing = client.post("/api/voice/transcribe", headers={"content-type": "audio/webm"}, content=b"")
    assert missing.status_code == 400
    too_large = client.post("/api/voice/transcribe", content=b"a" * (MAX_AUDIO_BYTES + 1),
                            headers={"content-type": "audio/webm"})
    assert too_large.status_code == 413


def test_voice_transcription_endpoint_mocked():
    with patch("fa_agents.webapp.transcribe_audio", return_value="Qual é o drawdown do BTC?") as transcribe:
        response = client.post("/api/voice/transcribe", content=b"fake audio stream",
                               headers={"content-type": "audio/webm"})
    assert response.status_code == 200, response.text
    assert response.json()["text"] == "Qual é o drawdown do BTC?"
    transcribe.assert_called_once_with(b"fake audio stream", "audio/webm")


def test_voice_speech_endpoint_mocked():
    with patch("fa_agents.webapp.synthesize_speech", return_value=b"mp3-bytes") as synth:
        r = client.post("/api/voice/speak", json={"text": "Backtest experimental."})
    assert r.status_code == 200
    assert r.content == b"mp3-bytes"
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert r.headers["cache-control"] == "no-store"
    synth.assert_called_once()


def test_voice_rejects_oversized_speech_or_foreign_origin():
    assert client.post("/api/voice/speak", json={"text": "a" * 2201}).status_code == 422
    response = client.post("/api/voice/speak", json={"text": "Olá"},
                           headers={"Origin": "https://different.example"})
    assert response.status_code == 403


def test_server_side_transcription_uses_gpt_transcribe():
    observed = {}
    class DummyTranscriptions:
        def create(self, **kw):
            observed.update(kw)
            return SimpleNamespace(text="Vamos analisar a NVDA.")
    fake = SimpleNamespace(audio=SimpleNamespace(transcriptions=DummyTranscriptions()))
    with patch("fa_agents.voice._client", return_value=fake):
        text = transcribe_audio(b"fake", "audio/webm")
    assert text == "Vamos analisar a NVDA."
    assert observed["model"] == "gpt-transcribe"
    assert observed["file"].name == "voice.webm"


def test_server_side_speech_uses_tts_without_persisting():
    observed = {}
    class DummySpeech:
        def create(self, **kw):
            observed.update(kw)
            return SimpleNamespace(read=lambda: b"mp3 content")
    fake = SimpleNamespace(audio=SimpleNamespace(speech=DummySpeech()))
    with patch("fa_agents.voice._client", return_value=fake):
        result = synthesize_speech("Resultado da estratégia.")
    assert result == b"mp3 content"
    assert observed["model"] == "gpt-4o-mini-tts"
    assert observed["voice"] == "cedar"


def test_error_contains_no_audio_or_api_credentials():
    with pytest.raises(VoiceError):
        transcribe_audio(b"fake", "application/json")
    with pytest.raises(VoiceError):
        synthesize_speech("")
