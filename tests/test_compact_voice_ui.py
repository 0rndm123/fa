"""Keep the FA_Agent chat's two voice actions compact and distinct."""
from __future__ import annotations

from fastapi.testclient import TestClient

from fa_agents.webapp import app


def test_chat_voice_controls_are_compact_and_distinct():
    client = TestClient(app)
    html = client.get("/").text
    assert 'id="voiceToggle"' in html   # Dictation, user reviews transcript.
    assert 'id="voiceMic"' in html      # Turn-based spoken conversation.
    assert 'class="fa-wave-mini"' in html
    assert 'id="voiceTurnControls"' in html
    assert 'class="voice-turn-controls hidden"' in html
    assert 'id="voiceConversationPanel"' not in html
    assert 'id="voiceStop"' in html
    assert 'id="voiceAuto"' in html


def test_voice_icon_controls_keep_their_svg_and_waveform_when_used():
    client = TestClient(app)
    application = client.get("/static/app.js").text
    dialogue = client.get("/static/voice-turns.js").text
    styles = client.get("/static/styles.css").text
    assert 'button.textContent=recording?' not in application
    assert 'mic.textContent = next ===' not in dialogue
    assert 'voiceButton(recording)' in application
    assert 'mic.classList.toggle("active", next !== "idle")' in dialogue
    assert "fa-voice-bars" in styles
    assert "prefers-reduced-motion:reduce" in styles


def test_adaptive_mode_is_exposed_but_not_required_in_chat():
    client = TestClient(app)
    response = client.post("/api/analyze", json={
        "symbol": "DEMO", "mode": "demo", "asset_class": "equity",
        "agents": ["risk"], "question": "Analyze risk.",
    })
    assert response.status_code == 200
    report = response.json()["report"]
    assert report["research_plan"]["mode"] == "adaptive"
    assert report["critical_review"]["status"] in {"clear", "caution", "insufficient"}
    assert report["research_plan"]["followup_agents"] == []
