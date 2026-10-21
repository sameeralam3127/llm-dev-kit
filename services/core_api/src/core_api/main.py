"""core-api's FastAPI app: wiring only. Each layer gets its collaborators here."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from core_api.adapters.postgres import PostgresStore
from core_api.api import api_keys, documents, workspaces
from core_api.config import Settings
from core_api.services.api_keys import ApiKeyService
from core_api.services.auth import AccessResolver
from core_api.services.documents import DocumentService
from core_api.services.workspaces import WorkspaceService
from devkit_common.http import install_service
from ldk_core.plugins import AUTH, PluginKind, PluginRegistry
from ldk_core.ports import AuthProvider


def session_verifier(settings: Settings) -> tuple[AuthProvider, PluginRegistry]:
    """The v2 ``auth.local`` plugin, from the registry, configured for the web app's tokens."""
    registry = PluginRegistry()
    registry.load_entry_points()
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
    return registry.get(AUTH, "local"), registry


def create_app(settings: Settings, *, sessions: AuthProvider | None = None) -> FastAPI:
    """Build the app. Tests pass their own ``sessions`` verifier."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = AsyncConnectionPool(settings.database_url, open=False, min_size=1, max_size=10)
        await pool.open()
        registry = None
        verifier = sessions
        if verifier is None:
            verifier, registry = session_verifier(settings)
        store = PostgresStore(pool)
        pepper = settings.api_key_pepper.get_secret_value().encode()
        app.state.resolver = AccessResolver(
            sessions=verifier, keys=store, workspaces=store, pepper=pepper
        )
        app.state.workspaces = WorkspaceService(workspaces=store, audit=store)
        app.state.api_keys = ApiKeyService(keys=store, audit=store, pepper=pepper)
        app.state.documents = DocumentService(documents=store, audit=store)
        try:
            yield
        finally:
            if registry is not None:
                await registry.aclose()
            await pool.close()

    app = FastAPI(title="LLM Dev Kit — core-api", version="0.1.0", lifespan=lifespan)
    install_service(app, service="core-api", settings=settings)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "core-api"}

    app.include_router(workspaces.router)
    app.include_router(api_keys.router)
    app.include_router(documents.router)
    return app
