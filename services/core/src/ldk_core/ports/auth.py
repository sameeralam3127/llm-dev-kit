"""``AuthProvider``: a bearer credential to a verified identity.

Backends verify every request themselves and never trust the gateway
(decision D2). Implementations land in Phase 4: ``auth_local`` verifies the
web app's RS256 tokens via JWKS, ``auth_oidc`` any OIDC issuer, and personal
``sk-ldk-`` API keys are checked against their stored hashes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

PrincipalKind = Literal["user", "service", "api_key"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is calling, as established by an :class:`AuthProvider`.

    Attributes:
        subject: Stable user or service id (the token's ``sub``).
        kind: How the caller authenticated.
        roles: Coarse RBAC roles: ``admin``, ``user``, ``viewer``.
        scopes: Fine-grained permissions granted to this credential.
        claims: The verified claims, for audit. Never trusted for access
            decisions beyond what ``roles`` and ``scopes`` already express.
    """

    subject: str
    kind: PrincipalKind
    roles: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    claims: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def has_role(self, role: str) -> bool:
        """Return whether this principal holds ``role``."""
        return role in self.roles


@runtime_checkable
class AuthProvider(Protocol):
    """Verifies one kind of credential."""

    @property
    def name(self) -> str:
        """Registry name, e.g. ``"local"``, ``"oidc"``."""
        ...

    def accepts(self, credential: str) -> bool:
        """Cheaply decide whether this provider should try ``credential``.

        Lets several providers coexist: an API-key provider claims
        ``sk-ldk-...``, a JWT provider claims three dot-separated segments.
        """
        ...

    async def authenticate(self, credential: str) -> Principal:
        """Verify ``credential`` and return the caller.

        Raises:
            ldk_core.errors.ServiceError: ``unauthorized`` for any invalid,
                expired or revoked credential, with no detail about which.
        """
        ...
