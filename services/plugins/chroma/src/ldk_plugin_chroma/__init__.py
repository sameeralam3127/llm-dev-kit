"""llm-dev-kit plugin: ChromaDB as a vector store (``vector_store.chroma``)."""

from collections.abc import Mapping
from typing import Any

from ldk_core.plugins import Plugin, load_manifest
from ldk_plugin_chroma.store import ChromaVectorStore


def _factory(config: Mapping[str, Any]) -> ChromaVectorStore:
    return ChromaVectorStore(
        config["host"],
        config.get("port", 8000),
        collection_prefix=config.get("collection_prefix", ""),
    )


plugin = Plugin(load_manifest(__name__, "manifests/vector_store.chroma.json"), _factory)

__all__ = ["ChromaVectorStore", "plugin"]
