"""Cloudflare Access verification for optional, independently hosted FA_Agent.

Do not trust CF-Connecting-IP or a bare identity header: only a signed JWT from
the configured Cloudflare Access team is accepted. The default app stays local.
"""
from __future__ import annotations

from functools import lru_cache
import os
import re

TEAM_DOMAIN = re.compile(r"^[a-z0-9-]+\.cloudflareaccess\.com$")
PUBLIC_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")


def remote_mode() -> bool:
    return os.getenv("FA_REMOTE_AUTH_MODE", "").strip().lower() == "cloudflare_access"


def remote_configuration() -> tuple[str, str, str]:
    team = os.getenv("FA_CF_ACCESS_TEAM_DOMAIN", "").strip().lower()
    aud = os.getenv("FA_CF_ACCESS_AUD", "").strip()
    host = os.getenv("FA_TUNNEL_HOSTNAME", "").strip().lower()
    if not TEAM_DOMAIN.fullmatch(team):
        raise ValueError("Cloudflare Access team domain is missing or invalid.")
    if not aud or len(aud) > 256 or not re.fullmatch(r"[A-Za-z0-9_-]+", aud):
        raise ValueError("Cloudflare Access application AUD is missing or invalid.")
    if not PUBLIC_HOST.fullmatch(host) or host.startswith("localhost") or host.endswith(".local"):
        raise ValueError("FA_TUNNEL_HOSTNAME must be a valid public hostname.")
    return team, aud, host


@lru_cache(maxsize=4)
def _jwk_client(team: str):
    from jwt import PyJWKClient
    return PyJWKClient(
        f"https://{team}/cdn-cgi/access/certs",
        cache_jwk_set=True, lifespan=300, timeout=5,
    )


def verify_access_jwt(token: str, *, team: str, aud: str) -> bool:
    if not token or len(token) > 8192:
        return False
    try:
        import jwt
        key = _jwk_client(team).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=f"https://{team}",
            audience=aud,
            options={"require": ["exp", "iat", "iss", "aud"]},
            leeway=30,
        )
        return bool(payload.get("sub"))
    except Exception:
        # Fail closed on invalid signatures, bad claims, network and key errors.
        return False
