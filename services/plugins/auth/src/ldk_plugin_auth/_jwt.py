"""JWT verification shared by the auth providers: a key set and claim checks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import jwt

from ldk_core.auth import unauthorized
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.observability import get_logger, outgoing_headers

_log = get_logger(__name__)

ASYMMETRIC_ALGORITHMS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384")
"""Accepted signature algorithms. Never ``none`` and never HMAC: a shared
secret would let anyone who can verify also sign."""

LEEWAY_SECONDS = 30
"""Clock skew tolerated on ``exp``, ``nbf`` and ``iat``."""


def peek_issuer(token: str) -> str | None:
    """Return a JWT's ``iss`` without verifying anything, or ``None``.

    Only for routing a token to the provider that can verify it; the provider
    then checks the signature and the issuer properly.
    """
    if token.count(".") != 2:
        return None
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return None
    issuer = claims.get("iss")
    return issuer if isinstance(issuer, str) else None


class KeySet:
    """A JSON Web Key Set fetched over HTTP, refreshed when a key is missing.

    Keys are cached for ``max_age`` seconds. A token signed with an unknown
    key id triggers a refetch, at most once per ``min_interval`` seconds, so
    key rotation is picked up without letting forged key ids hammer the
    issuer. Callers that need a refresh while one is running share it, so a
    cold start or a rotation fetches once, not once per concurrent request.

    Args:
        url: Returns the JWKS URL; called on each fetch, so it can be resolved
            lazily from an OIDC discovery document.
        client: Used for the fetch.
    """

    def __init__(
        self,
        url: Callable[[], Awaitable[str]],
        client: httpx.AsyncClient,
        *,
        max_age: float = 600.0,
        min_interval: float = 30.0,
    ) -> None:
        self._url = url
        self._client = client
        self._max_age = max_age
        self._min_interval = min_interval
        self._keys: dict[str | None, jwt.PyJWK] = {}
        self._fetched_at = float("-inf")
        self._refreshing: asyncio.Task[None] | None = None

    async def key(self, kid: str | None) -> jwt.PyJWK:
        """Return the signing key ``kid``.

        Raises:
            ServiceError: ``unauthorized`` if no such key exists after a
                refresh; ``upstream_unavailable`` if the set cannot be fetched.
        """
        now = time.monotonic()
        stale = now - self._fetched_at > self._max_age
        missing = kid not in self._keys
        if stale or (missing and now - self._fetched_at > self._min_interval):
            await self._refresh_once()
        key = self._keys.get(kid)
        if key is None:
            raise unauthorized()
        return key

    async def _refresh_once(self) -> None:
        """Join the refresh in flight, or start one; its failure is shared too.

        The fetch runs as its own task, so a caller that is cancelled does not
        cancel it for the others. Once it finishes the slot is free again, so
        the next caller after a failure retries.
        """
        if self._refreshing is None:
            self._refreshing = asyncio.create_task(self._refresh_and_release())
        await asyncio.shield(self._refreshing)

    async def _refresh_and_release(self) -> None:
        try:
            await self._refresh()
        finally:
            self._refreshing = None

    async def _refresh(self) -> None:
        url = await self._url()
        try:
            res = await self._client.get(url, headers=outgoing_headers())
            res.raise_for_status()
            data = res.json()
            keys = jwt.PyJWKSet.from_dict(data).keys
        except (httpx.HTTPError, ValueError, jwt.PyJWTError) as exc:
            _log.warning("could not fetch signing keys", exception_type=type(exc).__name__)
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE, "Identity service unavailable"
            ) from exc
        self._keys = {key.key_id: key for key in keys if key.public_key_use in (None, "sig")}
        # A set with a single key and no ids still verifies tokens without one.
        if len(keys) == 1 and keys[0].key_id is None:
            self._keys[None] = keys[0]
        self._fetched_at = time.monotonic()


async def verify(
    token: str,
    keys: KeySet,
    *,
    issuer: str,
    audience: str,
) -> dict[str, Any]:
    """Verify ``token``'s signature, issuer, audience and lifetime.

    Returns:
        The verified claims.

    Raises:
        ServiceError: ``unauthorized`` for any invalid token, without saying
            which check failed; the reason is logged at debug level.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        _log.debug("rejected token", exception_type=type(exc).__name__)
        raise unauthorized() from exc
    algorithm = header.get("alg")
    if algorithm not in ASYMMETRIC_ALGORITHMS:
        _log.debug("rejected token", reason="algorithm not allowed")
        raise unauthorized()

    key = await keys.key(header.get("kid"))
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key.key,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        _log.debug("rejected token", exception_type=type(exc).__name__)
        raise unauthorized() from exc
    return claims
