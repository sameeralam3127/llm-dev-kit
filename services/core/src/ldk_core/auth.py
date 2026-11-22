"""Authentication: from an ``Authorization`` header to a :class:`Principal`.

Every service verifies its callers itself and never trusts the gateway
(decision D2). An :class:`Authenticator` holds the configured
:class:`~ldk_core.ports.AuthProvider` plugins and asks the first one that
accepts a credential to verify it.

Access is decided by scope. The web app derives a token's scopes from the
user's role, so a role is a bundle of scopes:

- ``viewer``: ``chat``
- ``user``: ``chat``, ``ingest``
- ``admin``: ``chat``, ``ingest``, ``admin``

``ALLOW_LEGACY_ANONYMOUS`` keeps the pre-v2 behaviour, where any caller could
do anything, for one release. Each anonymous request is logged as a warning.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.observability.logging import get_logger
from ldk_core.ports.auth import AuthProvider, Principal

CHAT = "chat"
"""Ask questions and list models."""
INGEST = "ingest"
"""Add documents to the index."""
ADMIN = "admin"
"""Clear the index and the cache, read service statistics."""

ROLES = ("viewer", "user", "admin")
"""Every role, from least to most privileged."""

SCOPES_BY_ROLE: dict[str, frozenset[str]] = {
    "viewer": frozenset({CHAT}),
    "user": frozenset({CHAT, INGEST}),
    "admin": frozenset({CHAT, INGEST, ADMIN}),
}
"""The scopes each role grants."""

API_KEY_PREFIX = "sk-ldk-"
"""Prefix of personal API keys issued by the web app."""

ANONYMOUS = Principal(
    subject="anonymous",
    kind="anonymous",
    roles=frozenset({"admin"}),
    scopes=SCOPES_BY_ROLE["admin"],
)
"""The caller under ``ALLOW_LEGACY_ANONYMOUS``: everything, as before v2."""

_log = get_logger(__name__)
_credential: ContextVar[str | None] = ContextVar("ldk_credential", default=None)


def scopes_for_roles(roles: Iterable[str]) -> frozenset[str]:
    """Return the union of the scopes granted by ``roles``; unknown roles grant none."""
    granted: set[str] = set()
    for role in roles:
        granted |= SCOPES_BY_ROLE.get(role, frozenset())
    return frozenset(granted)


def unauthorized(message: str = "Authentication required") -> ServiceError:
    """Build the 401 every invalid or missing credential gets.

    The message never says why a credential failed, so a caller cannot tell an
    expired token from a forged one.
    """
    return ServiceError(
        ErrorCode.UNAUTHORIZED, message, headers={"WWW-Authenticate": 'Bearer realm="llm-dev-kit"'}
    )


def forbidden(scope: str) -> ServiceError:
    """Build the 403 for a valid caller whose credential lacks ``scope``."""
    return ServiceError(ErrorCode.FORBIDDEN, f"This needs the '{scope}' permission")


def bearer_token(authorization: str | None) -> str | None:
    """Return the token from an ``Authorization: Bearer ...`` header, if any."""
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


class Authenticator:
    """Verifies callers with the configured providers.

    Args:
        providers: Tried in order; the first whose ``accepts`` returns true
            verifies the credential, and its verdict is final.
        allow_anonymous: ``ALLOW_LEGACY_ANONYMOUS``. A request with no
            credential, or with one no provider accepts (such as a pre-v2
            cloud key on ``/v1``), is let through as :data:`ANONYMOUS`. A
            credential a provider accepts but rejects is still a 401.
    """

    def __init__(self, providers: Sequence[AuthProvider], *, allow_anonymous: bool = False) -> None:
        self.providers = tuple(providers)
        self.allow_anonymous = allow_anonymous
        if allow_anonymous:
            _log.error(
                "ALLOW_LEGACY_ANONYMOUS is on: every request without a credential gets "
                "full admin access. Move clients to personal API keys; the setting is "
                "removed in 2.0.0.",
            )

    async def authenticate(self, authorization: str | None) -> Principal:
        """Return the caller described by an ``Authorization`` header value.

        Raises:
            ServiceError: ``unauthorized`` when there is no usable credential
                (and anonymous access is off) or the credential is invalid.
        """
        token = bearer_token(authorization)
        if token is not None:
            for provider in self.providers:
                if provider.accepts(token):
                    return await provider.authenticate(token)
        if self.allow_anonymous:
            _log.warning("anonymous request allowed by ALLOW_LEGACY_ANONYMOUS")
            return ANONYMOUS
        raise unauthorized()


def require_scope(principal: Principal, scope: str) -> Principal:
    """Return ``principal`` if it holds ``scope``.

    Raises:
        ServiceError: ``forbidden`` otherwise.
    """
    if not principal.has_scope(scope):
        raise forbidden(scope)
    return principal


def bind_credential(credential: str | None) -> None:
    """Make ``credential`` the one :func:`auth_headers` sends for this request.

    Call it once a request is authenticated. Each request runs in its own
    task, so the binding ends with the request.
    """
    _credential.set(credential)


@contextmanager
def credential_scope(credential: str | None) -> Iterator[None]:
    """Bind ``credential`` for a block of work that does not arrive over HTTP."""
    token = _credential.set(credential)
    try:
        yield
    finally:
        _credential.reset(token)


def auth_headers() -> dict[str, str]:
    """Headers that carry the current caller's identity to another service."""
    credential = _credential.get()
    return {"Authorization": f"Bearer {credential}"} if credential else {}


__all__ = [
    "ADMIN",
    "ANONYMOUS",
    "API_KEY_PREFIX",
    "CHAT",
    "INGEST",
    "ROLES",
    "SCOPES_BY_ROLE",
    "Authenticator",
    "auth_headers",
    "bearer_token",
    "bind_credential",
    "credential_scope",
    "forbidden",
    "require_scope",
    "scopes_for_roles",
    "unauthorized",
]
