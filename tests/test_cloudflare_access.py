"""Cloudflare Access mode is fail-closed and preserves the local-only default."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from fa_agents import cloudflare_access
from fa_agents.webapp import app

HOST = "fa.example.pt"
TEAM = "example.cloudflareaccess.com"
AUD = "abcdef0123456789"


def configure(monkeypatch):
    monkeypatch.setenv("FA_REMOTE_AUTH_MODE", "cloudflare_access")
    monkeypatch.setenv("FA_CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("FA_CF_ACCESS_AUD", AUD)
    monkeypatch.setenv("FA_TUNNEL_HOSTNAME", HOST)


def test_local_mode_unaffected(monkeypatch):
    monkeypatch.delenv("FA_REMOTE_AUTH_MODE", raising=False)
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/api/capabilities").status_code == 200


def test_remote_denies_everything_without_token(monkeypatch):
    configure(monkeypatch)
    client = TestClient(app, base_url=f"https://{HOST}")
    assert client.get("/").status_code == 401
    assert client.get("/static/app.js").status_code == 401
    assert client.get("/api/capabilities").status_code == 401
    assert client.post("/api/analyze", json={"symbol": "DEMO", "mode": "demo"}).status_code == 401


def test_spoofed_ip_headers_never_bypass_access(monkeypatch):
    configure(monkeypatch)
    client = TestClient(app, base_url=f"https://{HOST}")
    r = client.get("/", headers={"CF-Connecting-IP": "127.0.0.1", "CF-Access-Authenticated-User-Email": "example@example.com"})
    assert r.status_code == 401


def test_host_and_same_origin_required_even_with_a_valid_token(monkeypatch):
    configure(monkeypatch)
    with patch("fa_agents.cloudflare_access.verify_access_jwt", return_value=True) as validator:
        client = TestClient(app, base_url=f"https://{HOST}")
        good = client.get("/api/capabilities", headers={"Cf-Access-Jwt-Assertion": "valid"})
        assert good.status_code == 200
        validator.assert_called_with("valid", team=TEAM, aud=AUD)
        bad_origin = client.post(
            "/api/analyze",
            json={"symbol": "DEMO", "mode": "demo", "agents": []},
            headers={"Cf-Access-Jwt-Assertion": "valid", "Origin": "https://external.example"},
        )
        assert bad_origin.status_code == 403
        good_origin = client.post(
            "/api/analyze",
            json={"symbol": "DEMO", "mode": "demo", "agents": []},
            headers={"Cf-Access-Jwt-Assertion": "valid", "Origin": f"https://{HOST}"},
        )
        assert good_origin.status_code == 200
        localhost = TestClient(app).get("/", headers={"Cf-Access-Jwt-Assertion": "valid"})
        assert localhost.status_code == 403


def test_missing_or_unknown_remote_configuration_is_fail_closed(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("FA_CF_ACCESS_AUD", raising=False)
    r = TestClient(app, base_url=f"https://{HOST}").get("/")
    assert r.status_code == 503
    monkeypatch.setenv("FA_REMOTE_AUTH_MODE", "off-but-not-really")
    assert TestClient(app).get("/").status_code == 503


def test_verify_access_jwt_checks_signature_issuer_aud_and_expiry(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signing_key = SimpleNamespace(key=private_key.public_key())
    now = datetime.now(timezone.utc)
    base = {"sub": "authorized-user", "iss": f"https://{TEAM}",
            "aud": AUD, "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp())}
    client = SimpleNamespace(get_signing_key_from_jwt=lambda token: signing_key)
    with patch("fa_agents.cloudflare_access._jwk_client", return_value=client):
        valid = jwt.encode(base, private_key, algorithm="RS256", headers={"kid": "test"})
        assert cloudflare_access.verify_access_jwt(valid, team=TEAM, aud=AUD)
        assert not cloudflare_access.verify_access_jwt(valid, team=TEAM, aud="different")
        assert not cloudflare_access.verify_access_jwt(valid, team="another.cloudflareaccess.com", aud=AUD)
        expired = jwt.encode({**base, "exp": int((now - timedelta(minutes=5)).timestamp())},
                             private_key, algorithm="RS256", headers={"kid": "test"})
        assert not cloudflare_access.verify_access_jwt(expired, team=TEAM, aud=AUD)
        unsigned = jwt.encode(base, key="", algorithm="none")
        assert not cloudflare_access.verify_access_jwt(unsigned, team=TEAM, aud=AUD)


def test_launcher_requires_dedicated_config_and_access():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "START_FA_CLOUDFLARE.bat").read_text(encoding="utf-8")
    assert "FA_CF_ACCESS_TEAM_DOMAIN" in launcher
    assert "FA_CF_ACCESS_AUD" in launcher
    assert "FA_TUNNEL_CONFIG" in launcher
    assert "FA_REMOTE_AUTH_MODE=cloudflare_access" in launcher
    assert "cloudflared tunnel --config" in launcher
    assert "--url" not in launcher
