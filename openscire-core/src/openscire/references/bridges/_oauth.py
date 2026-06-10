# SPDX-License-Identifier: Apache-2.0

"""Shared OAuth2 helper for reference manager bridges.

Supports authorization code flow with PKCE.
Tokens are encrypted at rest via Fernet (AES-256-GCM) when cryptography is available.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import webbrowser
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from openscire.exceptions import ReferenceError
from openscire.logging import get_logger

logger = get_logger("openscire.references.bridges.oauth")

TOKEN_DIR = Path.home() / ".config" / "openscire"
TOKEN_FILE = TOKEN_DIR / "oauth_tokens.json"
KEY_FILE = TOKEN_DIR / "oauth.key"

# Fernet key embedded as a lazy import to keep cryptography optional
_FERNET: Any = None


def _ensure_key() -> bytes:
    """Load or generate a 256-bit Fernet key stored at ~/.config/openscire/oauth.key."""
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        key = KEY_FILE.read_bytes()
        if len(key) == 44:  # base64-encoded Fernet key
            return key
    key = urlsafe_b64encode(os.urandom(32))
    KEY_FILE.write_bytes(key)
    KEY_FILE.chmod(0o600)
    return key


def _encrypt_token(data: dict[str, object]) -> str:
    """Encrypt token dict to a base64 string using Fernet (AES-256-GCM)."""
    global _FERNET  # noqa: PLW0603
    if _FERNET is None:
        try:
            from cryptography.fernet import Fernet

            _FERNET = Fernet(_ensure_key())
        except ImportError:
            raise ReferenceError(
                "cryptography is required for OAuth token storage. "
                "Install it with: pip install cryptography",
                source="oauth",
            ) from None
    payload = json.dumps(data).encode("utf-8")
    return _FERNET.encrypt(payload).decode("utf-8")  # type: ignore[no-any-return]


def _decrypt_token(ciphertext: str) -> dict[str, object]:
    """Decrypt a Fernet-encrypted token string back to a dict."""
    global _FERNET  # noqa: PLW0603
    if _FERNET is None:
        try:
            from cryptography.fernet import Fernet

            _FERNET = Fernet(_ensure_key())
        except ImportError:
            raise ReferenceError(
                "cryptography is required for OAuth token decryption. "
                "Install it with: pip install cryptography",
                source="oauth",
            ) from None
    payload = _FERNET.decrypt(ciphertext.encode("utf-8"))
    return json.loads(payload.decode("utf-8"))  # type: ignore[no-any-return]


def _load_tokens() -> dict[str, dict[str, object]]:
    """Load all encrypted tokens from disk."""
    if not TOKEN_FILE.exists():
        return {}
    raw = TOKEN_FILE.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Corrupt OAuth token file, starting fresh")
        return {}
    decrypted: dict[str, dict[str, object]] = {}
    for key, val in data.items():
        if isinstance(val, str):
            try:
                decrypted[key] = _decrypt_token(val)
            except Exception:
                logger.warning("Failed to decrypt token for %s, skipping", key)
    return decrypted


def _save_tokens(tokens: dict[str, dict[str, object]]) -> None:
    """Encrypt and persist all tokens to disk."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    encrypted: dict[str, str] = {}
    for key, val in tokens.items():
        encrypted[key] = _encrypt_token(val)
    TOKEN_FILE.write_text(json.dumps(encrypted, indent=2))
    TOKEN_FILE.chmod(0o600)


@dataclass
class OAuth2Config:
    """OAuth2 configuration for a reference manager."""

    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    redirect_uri: str = "http://localhost:18080/callback"
    scopes: list[str] = field(default_factory=lambda: ["all"])


class OAuth2Helper:
    """Async OAuth2 authorization code flow with PKCE and encrypted token storage.

    Tokens are persisted to ~/.config/openscire/oauth_tokens.json encrypted with
    Fernet (AES-256-GCM). The encryption key is stored at ~/.config/openscire/oauth.key.
    """

    def __init__(
        self,
        config: OAuth2Config,
        bridge_id: str,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._config = config
        self._bridge_id = bridge_id
        self._client = http_client

    def _code_verifier(self) -> str:
        """Generate a PKCE code verifier (RFC 7636)."""
        return urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")

    def _code_challenge(self, verifier: str) -> str:
        """Derive a PKCE code challenge S256 from the verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    async def _start_auth_flow(self) -> None:  # pragma: no cover
        """Open the authorization URL in a browser (interactive flow)."""
        verifier = self._code_verifier()
        challenge = self._code_challenge(verifier)
        state = secrets.token_urlsafe(16)

        # Store PKCE state temporarily
        temp_state: dict[str, object] = {
            "verifier": verifier,
            "state": state,
        }
        tokens = _load_tokens()
        tokens[f"_pkce_{self._bridge_id}"] = temp_state
        _save_tokens(tokens)

        params = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": self._config.redirect_uri,
            "scope": " ".join(self._config.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        url = f"{self._config.authorize_url}?{httpx.QueryParams(params)}"
        logger.info("Opening browser for OAuth authorization: %s", url)
        webbrowser.open(url)

    async def _exchange_code(self, code: str, verifier: str) -> dict[str, object]:
        """Exchange authorization code for tokens."""
        response = await self._client.post(
            self._config.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._config.redirect_uri,
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
                "code_verifier": verifier,
            },
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            raise ReferenceError(
                f"Token exchange failed: {response.status_code} {response.text}",
                source="oauth",
            )
        return response.json()  # type: ignore[no-any-return]

    async def refresh_token(self, refresh_token: str) -> dict[str, object]:
        """Refresh an expired access token."""
        response = await self._client.post(
            self._config.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
            },
            headers={"Accept": "application/json"},
        )
        if response.status_code != 200:
            raise ReferenceError(
                f"Token refresh failed: {response.status_code}",
                source="oauth",
            )
        tokens: dict[str, object] = response.json()
        # Persist updated tokens
        all_tokens = _load_tokens()
        all_tokens[self._bridge_id] = tokens
        _save_tokens(all_tokens)
        return tokens

    async def get_access_token(self) -> str:
        """Retrieve a valid access token, refreshing if necessary.

        Returns:
            The current access token string (not Bearer-prefixed).
        """
        all_tokens = _load_tokens()
        tokens = all_tokens.get(self._bridge_id)
        if tokens is None:
            raise ReferenceError(
                f"No OAuth tokens found for {self._bridge_id}. Call authenticate() first.",
                source="oauth",
            )

        access_token = str(tokens.get("access_token", ""))
        expires_at = tokens.get("expires_at")
        refresh = tokens.get("refresh_token")

        # Check expiry (with 60s buffer)
        if expires_at is not None:
            try:
                expiry = datetime.fromtimestamp(float(str(expires_at)), tz=timezone.utc)  # noqa: UP017
                if expiry <= datetime.now(timezone.utc) and refresh:  # noqa: UP017
                    refreshed = await self.refresh_token(str(refresh))
                    access_token = str(refreshed.get("access_token", access_token))
            except (ValueError, TypeError):
                pass

        return access_token

    async def authenticate(self) -> bool:  # pragma: no cover
        """Interactive OAuth2 authorization code flow.

        Opens the browser for user authorization. Requires a local callback
        server to capture the authorization code.

        Returns:
            True if authentication succeeded.
        """
        # Check if a valid token already exists
        try:
            token = await self.get_access_token()
            if token:
                logger.info("Valid OAuth token exists for %s", self._bridge_id)
                return True
        except ReferenceError:
            pass

        await self._start_auth_flow()
        logger.info(
            "After authorizing, the callback code will be captured automatically. "
            "If running headless, manually retrieve the code from the redirect URL."
        )

        # Simple local callback server to capture the code
        code = await self._capture_callback()
        if not code:
            return False

        # Retrieve the PKCE verifier
        pkce_state = _load_tokens().get(f"_pkce_{self._bridge_id}", {})
        verifier = str(pkce_state.get("verifier", ""))

        tokens = await self._exchange_code(code, verifier)
        # Add expiry timestamp
        if "expires_in" in tokens:
            expires_in = int(str(tokens["expires_in"]))
            tokens["expires_at"] = str(
                datetime.now(timezone.utc).timestamp() + expires_in  # noqa: UP017
            )

        all_tokens = _load_tokens()
        all_tokens[self._bridge_id] = tokens
        all_tokens.pop(f"_pkce_{self._bridge_id}", None)
        _save_tokens(all_tokens)

        logger.info("OAuth authentication successful for %s", self._bridge_id)
        return True

    async def _capture_callback(self) -> str | None:  # pragma: no cover
        """Start a minimal HTTP server to capture the OAuth callback.

        Only works in interactive environments. Returns the authorization code
        or None if the callback was not received.
        """
        import asyncio
        from urllib.parse import parse_qs, urlparse

        code: str | None = None
        server: Any = None

        async def _handle(request: Any) -> bytes:  # noqa: ANN401
            nonlocal code, server
            parsed = urlparse(str(request.url))
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            if server:
                server.close()
            return b"Authorization complete. You can close this window."

        try:
            from aiohttp import web

            app = web.Application()
            app.router.add_get("/callback", _handle)  # type: ignore[arg-type]
            runner = web.AppRunner(app)
            await runner.setup()
            # Use a specific port
            site = web.TCPSite(runner, "localhost", 18080)
            await site.start()
            server = site
            # Wait up to 120s for callback
            for _ in range(120):
                if code is not None:
                    break
                await asyncio.sleep(1)
            await runner.cleanup()
        except ImportError:
            logger.warning("aiohttp not available. Paste the full redirect URL: ")
            # Fallback: prompt user to paste callback URL
            callback_url = input("Paste the full callback URL: ").strip()
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]

        return code
