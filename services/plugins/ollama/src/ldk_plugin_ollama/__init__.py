"""llm-dev-kit plugin: Ollama for chat (``llm.ollama``) and embeddings (``embedder.ollama``)."""

from collections.abc import Mapping
from typing import Any

from ldk_core.plugins import Plugin, load_manifest
from ldk_plugin_ollama.embedder import KNOWN_DIMENSIONS, OllamaEmbedder
from ldk_plugin_ollama.provider import OllamaProvider


def _provider(config: Mapping[str, Any]) -> OllamaProvider:
    return OllamaProvider(config["host"], timeout_seconds=config.get("timeout_seconds", 120))


def _embedder(config: Mapping[str, Any]) -> OllamaEmbedder:
    return OllamaEmbedder(
        config["host"],
        model=config.get("model", "nomic-embed-text"),
        dimension=config.get("dimension"),
        timeout_seconds=config.get("timeout_seconds", 120),
    )


llm_plugin = Plugin(load_manifest(__name__, "manifests/llm.ollama.json"), _provider)
embedder_plugin = Plugin(load_manifest(__name__, "manifests/embedder.ollama.json"), _embedder)

__all__ = ["KNOWN_DIMENSIONS", "OllamaEmbedder", "OllamaProvider", "embedder_plugin", "llm_plugin"]
