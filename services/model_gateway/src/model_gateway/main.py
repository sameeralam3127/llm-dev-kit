"""model-gateway's FastAPI app: wiring only.

Sovereign mode is enforced twice. The cloud plugins are never even imported
(importing LiteLLM is enough for it to fetch a file from GitHub), and the
gateway refuses every egress route whatever happens to be loaded.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from importlib.metadata import EntryPoint, entry_points

from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from core_api.adapters.postgres import PostgresStore
from core_api.ports.stores import AuditSink
from devkit_common.http import install_service
from ldk_core.observability import get_logger
from ldk_core.plugins import EMBEDDER, LLM, PluginKind, PluginRegistry
from ldk_core.plugins.discovery import ENTRY_POINT_GROUP
from ldk_core.ports import Embedder, LLMProvider
from model_gateway import api
from model_gateway.config import Settings
from model_gateway.domain import callers
from model_gateway.domain.egress import LOCAL_PROVIDER
from model_gateway.gateway import ModelGateway

_log = get_logger(__name__)

LOCAL_PLUGINS = frozenset({f"llm.{LOCAL_PROVIDER}", f"embedder.{LOCAL_PROVIDER}"})


def plugin_entry_points(settings: Settings) -> list[EntryPoint]:
    """The entry points to load: the local plugins, plus cloud ones that have a key.

    Anything not listed is never imported, so in sovereign mode no cloud
    client library is loaded at all.
    """
    wanted = LOCAL_PLUGINS | {f"llm.{name}" for name in settings.cloud_keys()}
    return [ep for ep in entry_points(group=ENTRY_POINT_GROUP) if ep.name in wanted]


def build_models(
    settings: Settings,
) -> tuple[PluginRegistry, dict[str, LLMProvider], Embedder]:
    """Load and configure the model plugins this deployment may use."""
    # LiteLLM downloads its model price list on import unless told not to.
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    registry = PluginRegistry()
    registry.load_entry_points(eps=plugin_entry_points(settings))
    timeout = settings.request_timeout_seconds
    registry.configure(
        PluginKind.LLM, LOCAL_PROVIDER, {"host": settings.ollama_host, "timeout_seconds": timeout}
    )
    registry.configure(
        PluginKind.EMBEDDER,
        LOCAL_PROVIDER,
        {
            "host": settings.ollama_host,
            "model": settings.embed_model,
            "dimension": settings.embed_dimension,
            "timeout_seconds": timeout,
        },
    )
    for name, key in settings.cloud_keys().items():
        base_url = settings.openai_base_url if name == "openai" else None
        registry.configure(
            PluginKind.LLM,
            name,
            {"api_key": key, "base_url": base_url, "timeout_seconds": timeout},
        )
    llms = {name: registry.get(LLM, name) for name in registry.names(LLM)}
    return registry, llms, registry.get(EMBEDDER, LOCAL_PROVIDER)


def create_app(
    settings: Settings,
    *,
    llms: Mapping[str, LLMProvider] | None = None,
    embedder: Embedder | None = None,
    audit: AuditSink | None = None,
) -> FastAPI:
    """Build the app. Tests pass their own providers, embedder or audit sink."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        registry = None
        if llms is None or embedder is None:
            registry, built_llms, built_embedder = build_models(settings)
        pool = None
        sink = audit
        if sink is None:
            pool = AsyncConnectionPool(settings.database_url, open=False, min_size=1, max_size=4)
            await pool.open()
            sink = PostgresStore(pool)
        app.state.services = [
            callers.core_api(settings.core_api_token.get_secret_value()),
            callers.ingest_worker(settings.ingest_worker_token.get_secret_value()),
        ]
        app.state.gateway = ModelGateway(
            llms=llms if llms is not None else built_llms,
            embedder=embedder or built_embedder,
            audit=sink,
            sovereign=settings.sovereign_mode,
            embed_max_texts=settings.embed_max_texts,
        )
        if settings.sovereign_mode:
            _log.info("sovereign mode on: cloud models are refused")
        else:
            _log.warning("sovereign mode off: cloud calls are allowed and audited as egress")
        try:
            yield
        finally:
            if registry is not None:
                await registry.aclose()
            if pool is not None:
                await pool.close()

    app = FastAPI(title="LLM Dev Kit — model-gateway", version="0.1.0", lifespan=lifespan)
    install_service(app, service="model-gateway", settings=settings)

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "model-gateway",
            "sovereign_mode": settings.sovereign_mode,
        }

    app.include_router(api.router)
    return app
