"""HEB mobile OAuth/PKCE — the durable, Incapsula-free auth path.

Ported from iHildy/heb-sdk-unofficial (`heb-auth`). HEB's mobile app authenticates
against the OIDC IdP at ``accounts.heb.com`` (a SEPARATE host from the
Incapsula-gated ``www.heb.com``) using OAuth2 Authorization-Code + PKCE, yielding a
**bearer access token + a long-lived refresh token**. Bearer-authed GraphQL calls
to the mobile API are NOT subject to the reese84/Incapsula web challenge — so this
replaces the Playwright/reese84 session dance entirely:

  one interactive login (human, once) -> refresh token -> refresh_tokens() forever.

Flow:
  1. ctx = create_oauth_context(); url = build_auth_url(ctx)
  2. Human opens `url`, signs in at accounts.heb.com, approves consent. The IdP
     redirects to ``com.heb.myheb://oauth2redirect?code=...`` (the iOS app deep
     link — the browser can't follow it; capture the `code` from that redirect).
  3. tokens = exchange_code(code, ctx.code_verifier)  -> access/refresh/id tokens
  4. later: tokens = refresh_tokens(tokens.refresh_token)  -> fresh access token
     (cheap HTTP, no browser, no Incapsula). Persist the rotated refresh_token.

Verified 2026-05-23: a token minted this way reads the live account + cart while
www.heb.com was anti-bot-hot. See ~/.claude/plans/heb-oauth-pkce-adoption.md.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

# Mobile (iOS) client config — from heb-auth-unofficial DEFAULT_HEB_OAUTH_CONFIG.
CLIENT_ID = "myheb-ios-prd"
REDIRECT_URI = "com.heb.myheb://oauth2redirect"
SCOPE = "openid profile email"
AUTH_URL = "https://accounts.heb.com/oidc/auth"
TOKEN_URL = "https://accounts.heb.com/oidc/token"
# The app's UA — sent on the token endpoint; harmless if the IdP ignores it.
OAUTH_USER_AGENT = "MyHEB/5.9.0.60733 (iOS 18.7.2; iPhone16,2) CFNetwork/1.0 Darwin/24.6.0"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def create_pkce_verifier() -> str:
    """RFC 7636 code_verifier: 43-char base64url of 32 random bytes."""
    return _b64url(secrets.token_bytes(32))


def create_pkce_challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


@dataclass
class OAuthContext:
    code_verifier: str
    code_challenge: str
    state: str
    nonce: str
    client_request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_amp_device_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_amp_session_id: str = field(default_factory=lambda: str(int(time.time() * 1000)))
    code_challenge_method: str = "S256"


def create_oauth_context() -> OAuthContext:
    verifier = create_pkce_verifier()
    return OAuthContext(
        code_verifier=verifier,
        code_challenge=create_pkce_challenge(verifier),
        state=_b64url(secrets.token_bytes(24)),
        nonce=_b64url(secrets.token_bytes(24)),
    )


def build_auth_url(ctx: OAuthContext, prompt: str | None = None) -> str:
    """Build the accounts.heb.com authorize URL. ``prompt`` may be
    'login' | 'consent' | 'none' (omit to use the IdP default)."""
    from urllib.parse import urlencode

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "code_challenge": ctx.code_challenge,
        "code_challenge_method": ctx.code_challenge_method,
        "state": ctx.state,
        "nonce": ctx.nonce,
        "client_request_id": ctx.client_request_id,
        "clientAmpDeviceId": ctx.client_amp_device_id,
        "clientAmpSessionId": ctx.client_amp_session_id,
    }
    if prompt:
        params["prompt"] = prompt
    return f"{AUTH_URL}?{urlencode(params)}"


def _post_token(body: dict[str, str]) -> dict[str, Any]:
    resp = httpx.post(
        TOKEN_URL,
        data=body,
        headers={
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "user-agent": OAUTH_USER_AGENT,
        },
        timeout=20.0,
    )
    if resp.status_code >= 400:
        raise OAuthError(f"HEB OAuth {resp.status_code}: {resp.text[:300]}")
    data: dict[str, Any] = resp.json()
    return data


def exchange_code(code: str, code_verifier: str) -> dict[str, Any]:
    """Authorization-code -> tokens. Returns the raw token response
    (access_token, refresh_token, id_token, expires_in, token_type, scope)."""
    return _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
        }
    )


def refresh_tokens(refresh_token: str) -> dict[str, Any]:
    """Refresh-token -> fresh tokens (cheap HTTP; no browser/Incapsula).
    Note: HEB rotates the refresh_token — persist the new one from the response."""
    return _post_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
        }
    )


class OAuthError(Exception):
    """An HEB OIDC token-endpoint error."""
