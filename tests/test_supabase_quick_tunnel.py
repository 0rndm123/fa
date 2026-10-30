"""No external calls: Supabase Quick Tunnel must fail closed."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from fa_agents.webapp import app
from fa_agents.supabase_auth import AccessDenied


def test_local_mode_has_no_login_requirement(monkeypatch):
    monkeypatch.delenv("FA_REMOTE_AUTH_MODE", raising=False)
    c=TestClient(app)
    assert c.get("/").status_code==200
    assert c.get("/api/capabilities").status_code==200
    assert c.get("/api/auth/config").json()=={"enabled":False}


def test_remote_mode_requires_bearer_for_every_api(monkeypatch):
    monkeypatch.setenv("FA_REMOTE_AUTH_MODE","supabase")
    monkeypatch.setenv("FA_SUPABASE_URL","https://sample.supabase.co")
    monkeypatch.setenv("FA_SUPABASE_PUBLISHABLE_KEY","sb_publishable_fake_test")
    c=TestClient(app,base_url="https://sample.trycloudflare.com")
    assert c.get("/").status_code==200
    assert c.get("/static/auth.js").status_code==200
    config=c.get("/api/auth/config")
    assert config.status_code==200
    assert config.json()["enabled"] is True
    for path in ("/api/capabilities", "/api/model-settings", "/api/auth/me"):
        assert c.get(path).status_code==401
    assert c.post("/api/analyze",json={"symbol":"DEMO","mode":"demo"}).status_code==401
    assert c.get("/api/auth/me",headers={"CF-Connecting-IP":"127.0.0.1"}).status_code==401


def test_remote_scope_separates_admin_and_user(monkeypatch):
    monkeypatch.setenv("FA_REMOTE_AUTH_MODE","supabase")
    monkeypatch.setenv("FA_SUPABASE_URL","https://sample.supabase.co")
    monkeypatch.setenv("FA_SUPABASE_PUBLISHABLE_KEY","sb_publishable_fake_test")
    headers={"Authorization":"Bearer sample.test.signature"}
    c=TestClient(app,base_url="https://sample.trycloudflare.com")
    with patch("fa_agents.supabase_auth.verify_access",
               new=AsyncMock(return_value={"subject":"id","email":"test@example.com","role":"user"})):
        assert c.get("/api/auth/me",headers=headers).json()["role"]=="user"
        assert c.get("/api/model-settings",headers=headers).status_code==200
        assert c.put("/api/model-settings",headers=headers,json={}).status_code==403
        assert c.post("/api/analyze",headers={**headers,"Origin":"https://evil.example"},
                      json={"symbol":"DEMO","mode":"demo"}).status_code==403
        assert c.get("/api/capabilities",headers=headers).status_code==200
    with patch("fa_agents.supabase_auth.verify_access",
               new=AsyncMock(return_value={"subject":"id","email":"test@example.com","role":"admin"})):
        assert c.get("/api/auth/me",headers=headers).json()["role"]=="admin"


def test_remote_invalid_token_denied(monkeypatch):
    monkeypatch.setenv("FA_REMOTE_AUTH_MODE","supabase")
    monkeypatch.setenv("FA_SUPABASE_URL","https://sample.supabase.co")
    monkeypatch.setenv("FA_SUPABASE_PUBLISHABLE_KEY","sb_publishable_fake_test")
    c=TestClient(app)
    with patch("fa_agents.supabase_auth.verify_access",
               new=AsyncMock(side_effect=AccessDenied("No FA permission"))):
        assert c.get("/api/capabilities",headers={"Authorization":"Bearer test"}).status_code==403


def test_quick_launcher_never_exposes_app_without_auth():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    launcher=(root/"START_FA_QUICK_TUNNEL.bat").read_text(encoding="utf-8")
    assert 'FA_REMOTE_AUTH_MODE=supabase' in launcher
    assert 'FA_SUPABASE_URL' in launcher
    assert 'FA_SUPABASE_PUBLISHABLE_KEY' in launcher
    assert 'cloudflared tunnel --url http://127.0.0.1:8300' in launcher
    html=(root/"src/fa_agents/web/index.html").read_text(encoding="utf-8")
    assert 'id="faLoginForm"' in html
    assert 'src="/static/auth.js"' in html
