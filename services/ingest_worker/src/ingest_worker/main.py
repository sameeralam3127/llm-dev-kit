"""The worker process: wire the ports, then loop over due jobs.

Run several replicas for more throughput: ``SKIP LOCKED`` makes them share the
queue without ever taking the same job.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from psycopg_pool import AsyncConnectionPool

from core_api.adapters.gateway import GatewayEmbedder
from core_api.adapters.postgres import PostgresStore
from ingest_worker.config import Settings
from ingest_worker.pipeline import process_next
from ldk_core.config import load_settings
from ldk_core.observability import configure_logging, get_logger
from ldk_core.plugins import CHUNKER, LOADER, PluginKind, PluginRegistry

#: Which plugins fill the Parser and Chunker ports in Milestone 1.
LOADER_PLUGIN = "pdf"
CHUNKER_PLUGIN = "fixed"

_log = get_logger(__name__)


async def run(settings: Settings, stop: asyncio.Event) -> None:
    """Process jobs until ``stop`` is set."""
    registry = PluginRegistry()
    registry.load_entry_points()
    registry.configure(PluginKind.LOADER, LOADER_PLUGIN, {})
    registry.configure(PluginKind.CHUNKER, CHUNKER_PLUGIN, {"size": 500, "overlap": 50})
    loader = registry.get(LOADER, LOADER_PLUGIN)
    chunker = registry.get(CHUNKER, CHUNKER_PLUGIN)
    embedder = GatewayEmbedder(
        settings.model_gateway_url,
        settings.model_gateway_token.get_secret_value(),
        model=settings.embed_model,
        dimension=settings.embed_dimension,
    )

    async with AsyncConnectionPool(settings.database_url, min_size=1, max_size=4) as pool:
        store = PostgresStore(pool)
        _log.info("worker started", worker=settings.worker_id)
        try:
            while not stop.is_set():
                if reclaimed := await store.reclaim_expired(settings.lease_seconds):
                    _log.warning("requeued abandoned jobs", count=reclaimed)
                outcome = await process_next(
                    queue=store,
                    store=store,
                    loader=loader,
                    chunker=chunker,
                    embedder=embedder,
                    worker_id=settings.worker_id,
                    batch_size=settings.embed_batch_size,
                )
                if outcome is None:
                    # Nothing due: wait, but wake at once on shutdown.
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(stop.wait(), timeout=settings.poll_seconds)
        finally:
            await embedder.aclose()
            await registry.aclose()
            _log.info("worker stopped", worker=settings.worker_id)


def main() -> None:
    """Entry point: ``python -m ingest_worker.main``. Stops cleanly on SIGTERM."""
    settings = load_settings(Settings)
    configure_logging(service="ingest-worker", level=settings.log_level, fmt=settings.log_format)

    async def _main() -> None:
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await run(settings, stop)

    asyncio.run(_main())


if __name__ == "__main__":
    main()
