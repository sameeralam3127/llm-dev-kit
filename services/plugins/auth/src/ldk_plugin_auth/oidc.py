"""``auth.oidc``: access tokens from any OpenID Connect issuer."""

from __future__ import annotations

from typing import Any

import httpx

from ldk_core.auth import ROLES, scopes_for_roles
from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.observability import get_logger, outgoing_headers
from ldk_core.ports import Principal
from ldk_plugin_auth._jwt import KeySet, peek_issuer, verify

_log = get_logger(__name__)


class OidcAuthProvider:
    """Verifies an OIDC issuer's access tokens, e.g. Keycloak's.

    The signing keys come from the issuer's discovery document. Roles are
    read from ``roles_claim`` (a dotted path; Keycloak puts realm roles at
    ``realm_access.roles``) and only ``viewer``, ``user`` and ``admin`` count.
    A token with none of them gets ``default_role``, or no access at all when
    that is ``None``.

    Args:
        issuer: Expected ``iss``, exactly as the issuer writes it.
        audience: Expected ``aud``. Keycloak needs an audience mapper on the
            client for this to appear in access tokens.
        discovery_url: Where to fetch the discovery document, when the
            issuer's public URL is not reachable from this service (as inside
            Docker). Defaults to ``{issuer}/.well-known/openid-configuration``.
        jwks_url: Skip discovery and fetch keys from here.
        roles_claim: Dotted path to a list of role names.
        default_role: Role for a verified token that names none.
        timeout: Seconds per request to the issuer.
        transport: For tests.
    """

    name = "oidc"

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        discovery_url: str | None = None,
        jwks_url: str | None = None,
        roles_claim: str = "realm_access.roles",
        default_role: str | None = "viewer",
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.issuer = issuer
        self.audience = audience
        self._discovery_url = (
            discovery_url or f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        )
        self._jwks_url = jwks_url
        self._roles_path = roles_claim.split(".")
        self._default_role = default_role
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)
        self._keys = KeySet(self._resolve_jwks_url, self._client)

    def accepts(self, credential: str) -> bool:
        """Claim tokens whose ``iss`` is this issuer."""
        return peek_issuer(credential) == self.issuer

    async def authenticate(self, credential: str) -> Principal:
        """Verify ``credential`` and map its roles."""
        claims = await verify(credential, self._keys, issuer=self.issuer, audience=self.audience)
        roles = self._roles(claims)
        return Principal(
            subject=str(claims["sub"]),
            kind="user",
            roles=roles,
            scopes=scopes_for_roles(roles),
            claims=claims,
            credential=credential,
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _roles(self, claims: dict[str, Any]) -> frozenset[str]:
        value: Any = claims
        for part in self._roles_path:
            value = value.get(part) if isinstance(value, dict) else None
        named = (
            frozenset(r for r in value if r in ROLES) if isinstance(value, list) else frozenset()
        )
        if named:
            return named
        return frozenset({self._default_role}) if self._default_role else frozenset()

    async def _resolve_jwks_url(self) -> str:
        if self._jwks_url:
            return self._jwks_url
        try:
            res = await self._client.get(self._discovery_url, headers=outgoing_headers())
            res.raise_for_status()
            document = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            _log.warning("OIDC discovery failed", exception_type=type(exc).__name__)
            raise ServiceError(
                ErrorCode.UPSTREAM_UNAVAILABLE, "Identity provider unavailable"
            ) from exc
        if document.get("issuer") != self.issuer:
            # A mismatch means the configuration is wrong; verifying against
            # these keys would accept tokens from somewhere else.
            _log.warning("OIDC discovery issuer mismatch")
            raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Identity provider misconfigured")
        jwks_uri = document.get("jwks_uri")
        if not isinstance(jwks_uri, str):
            raise ServiceError(ErrorCode.UPSTREAM_UNAVAILABLE, "Identity provider misconfigured")
        self._jwks_url = jwks_uri
        return jwks_uri
