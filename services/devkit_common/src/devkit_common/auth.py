"""Authentication for the FastAPI services.

``build_authenticator`` configures the auth plugins from settings at startup;
``require(scope)`` is the dependency every protected route declares::

    @app.post("/ingest/pdf")
    async def ingest(..., principal: Principal = Depends(require(INGEST))): ...

A route without it is public, which only ``/health`` should be.
"""

import ipaddress
from collections.abc import Awaitable, Callable

from fastapi import Request

from devkit_common.config import Settings
from ldk_core.auth import Authenticator, bind_credential, require_scope
from ldk_core.config import SettingsError
from ldk_core.plugins import AUTH, PluginKind, PluginRegistry
from ldk_core.ports import AuthProvider, Principal


def _is_loopback(host: str) -> bool:
    host = host.strip().removeprefix("[").removesuffix("]")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_legacy_anonymous(settings: Settings) -> None:
    """Refuse ``ALLOW_LEGACY_ANONYMOUS`` unless the gateway is loopback-only.

    Anonymous callers are administrators, so the setting must never be
    reachable from another machine.
    """
    if settings.allow_legacy_anonymous and not _is_loopback(settings.gateway_bind):
        raise SettingsError(
            "ALLOW_LEGACY_ANONYMOUS=true makes every caller without a credential an "
            f"administrator, and GATEWAY_BIND={settings.gateway_bind} exposes it to the "
            "network. Give your clients personal API keys and turn it off, or set "
            "GATEWAY_BIND=127.0.0.1. The setting is removed in 2.0.0."
        )


def build_authenticator(registry: PluginRegistry, settings: Settings) -> Authenticator:
    """Configure ``auth.local`` (and ``auth.oidc`` when an issuer is set)."""
    check_legacy_anonymous(settings)
    registry.configure(
        PluginKind.AUTH,
        "local",
        {
            "jwks_url": settings.auth_jwks_url,
            "token_url": settings.auth_token_url,
            "issuer": settings.auth_issuer,
            "audience": settings.auth_audience,
        },
    )
    providers: list[AuthProvider] = [registry.get(AUTH, "local")]

    if settings.auth_oidc_issuer:
        config: dict[str, str] = {
            "issuer": settings.auth_oidc_issuer,
            "audience": settings.auth_oidc_audience,
            "roles_claim": settings.auth_oidc_roles_claim,
        }
        if settings.auth_oidc_discovery_url:
            config["discovery_url"] = settings.auth_oidc_discovery_url
        registry.configure(PluginKind.AUTH, "oidc", config)
        providers.append(registry.get(AUTH, "oidc"))

    return Authenticator(providers, allow_anonymous=settings.allow_legacy_anonymous)


def require(scope: str) -> Callable[[Request], Awaitable[Principal]]:
    """Build a dependency that authenticates the caller and checks ``scope``.

    The verified caller is returned, kept on ``request.state.principal``, and
    bound so calls this request makes to other services carry its identity.
    """

    async def dependency(request: Request) -> Principal:
        authenticator: Authenticator = request.app.state.authenticator
        principal = await authenticator.authenticate(request.headers.get("authorization"))
        require_scope(principal, scope)
        bind_credential(principal.credential)
        request.state.principal = principal
        return principal

    return dependency
