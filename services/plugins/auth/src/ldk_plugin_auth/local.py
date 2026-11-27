"""``auth.local``: the web app's own tokens and personal API keys."""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

import httpx

from ldk_core.auth import API_KEY_PREFIX, ROLES, scopes_for_roles, unauthorized
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.observability import get_logger, outgoing_headers
from ldk_core.ports import Principal, PrincipalKind
from ldk_plugin_auth._jwt import KeySet, peek_issuer, verify

_log = get_logger(__name__)

EXCHANGE_CACHE_SECONDS = 60.0
"""How long an API key's exchanged token is reused. Bounds how long a revoked
key keeps working on a service that has already seen it."""

_MAX_CACHED_KEYS = 1024


class LocalAuthProvider:
    """Verifies tokens the web app signs, and exchanges API keys for them.

    The web app publishes its public keys at ``jwks_url`` and signs 5-minute
    RS256 access tokens carrying ``sub``, ``roles`` and ``scope``. A personal
    API key (``sk-ldk-...``) is sent to ``token_url``, which answers with such
    a token if the key is valid and not revoked; the result is cached for
    :data:`EXCHANGE_CACHE_SECONDS`, keyed by the key's hash.

    Args:
        jwks_url: The web app's ``/.well-known/jwks.json``.
        token_url: The web app's API-key exchange endpoint.
        issuer: Expected ``iss``.
        audience: Expected ``aud``.
        timeout: Seconds per request to the web app.
        transport: For tests.
    """

    name = "local"

    def __init__(
        self,
        *,
        jwks_url: str,
        token_url: str,
        issuer: str,
        audience: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self._token_url = token_url
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

        async def jwks() -> str:
            return jwks_url

        self._keys = KeySet(jwks, self._client)
        self._exchanged: dict[str, tuple[float, Principal]] = {}
        self._exchanging: dict[str, asyncio.Task[Principal]] = {}

    def accepts(self, credential: str) -> bool:
        """Claim API keys and tokens this web app issued."""
        return credential.startswith(API_KEY_PREFIX) or peek_issuer(credential) == self.issuer

    async def authenticate(self, credential: str) -> Principal:
        """Verify a token, or exchange and verify an API key."""
        if credential.startswith(API_KEY_PREFIX):
            return await self._from_api_key(credential)
        return await self._from_token(credential)

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _from_token(self, token: str) -> Principal:
        claims = await verify(token, self._keys, issuer=self.issuer, audience=self.audience)
        return _principal(claims, token)

    async def _from_api_key(self, key: str) -> Principal:
        digest = hashlib.sha256(key.encode()).hexdigest()
        cached = self._exchanged.get(digest)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        # Concurrent first uses of one key share a single exchange, success or
        # failure, keyed by the key's hash; it runs as its own task so one
        # cancelled caller does not cancel it for the rest.
        task = self._exchanging.get(digest)
        if task is None:
            task = asyncio.create_task(self._exchange_and_release(key, digest))
            self._exchanging[digest] = task
        return await asyncio.shield(task)

    async def _exchange_and_release(self, key: str, digest: str) -> Principal:
        try:
            return await self._exchange(key, digest)
        finally:
            self._exchanging.pop(digest, None)

    async def _exchange(self, key: str, digest: str) -> Principal:
        now = time.monotonic()
        try:
            res = await self._client.post(
                self._token_url,
                headers={"Authorization": f"Bearer {key}", **outgoing_headers()},
            )
        except httpx.HTTPError as exc:
            _log.warning("API key exchange failed", error=str(exc))
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE, "Identity service unavailable"
            ) from exc
        if res.status_code in (401, 403):
            raise unauthorized()
        if res.status_code != 200:
            _log.warning("API key exchange failed", status=res.status_code)
            raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Identity service unavailable")

        try:
            token = res.json()["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ServiceError(
                ErrorCode.UPSTREAM_ERROR, "Identity service sent an invalid response"
            ) from exc
        claims = await verify(token, self._keys, issuer=self.issuer, audience=self.audience)
        principal = _principal(claims, token)

        lifetime = float(claims["exp"]) - time.time() - 30
        if lifetime > 0:
            self._remember(digest, now + min(EXCHANGE_CACHE_SECONDS, lifetime), principal)
        return principal

    def _remember(self, digest: str, expires_at: float, principal: Principal) -> None:
        if len(self._exchanged) >= _MAX_CACHED_KEYS:
            now = time.monotonic()
            self._exchanged = {k: v for k, v in self._exchanged.items() if v[0] > now}
            if len(self._exchanged) >= _MAX_CACHED_KEYS:
                self._exchanged.pop(next(iter(self._exchanged)))
        self._exchanged[digest] = (expires_at, principal)


def _principal(claims: dict[str, Any], token: str) -> Principal:
    raw_roles = claims.get("roles")
    roles = (
        frozenset(r for r in raw_roles if r in ROLES)
        if isinstance(raw_roles, list)
        else frozenset()
    )
    raw_scope = claims.get("scope")
    granted = frozenset(raw_scope.split()) if isinstance(raw_scope, str) else frozenset()
    methods = claims.get("amr")
    kind: PrincipalKind = (
        "api_key" if isinstance(methods, list) and "api_key" in methods else "user"
    )
    return Principal(
        subject=str(claims["sub"]),
        kind=kind,
        roles=roles,
        # A token can narrow what its role allows, never widen it.
        scopes=granted & scopes_for_roles(roles),
        claims=claims,
        credential=token,
    )
