"""Typed keys tying each :class:`PluginKind` to its port protocol.

Pass one of these to :meth:`PluginRegistry.get` and the result is typed as
the port, e.g. ``registry.get(LLM, "ollama")`` is an ``LLMProvider``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ldk_core.plugins.manifest import PluginKind
from ldk_core.ports import (
    AuthProvider,
    Chunker,
    DocumentLoader,
    Embedder,
    LLMProvider,
    RateLimiter,
    StorageBackend,
    Tool,
    VectorStore,
)


@dataclass(frozen=True, slots=True)
class PortSpec[T]:
    """A plugin kind and the runtime-checkable protocol its plugins satisfy."""

    kind: PluginKind
    protocol: type[Any]


LLM: PortSpec[LLMProvider] = PortSpec(PluginKind.LLM, LLMProvider)
EMBEDDER: PortSpec[Embedder] = PortSpec(PluginKind.EMBEDDER, Embedder)
VECTOR_STORE: PortSpec[VectorStore] = PortSpec(PluginKind.VECTOR_STORE, VectorStore)
LOADER: PortSpec[DocumentLoader] = PortSpec(PluginKind.LOADER, DocumentLoader)
CHUNKER: PortSpec[Chunker] = PortSpec(PluginKind.CHUNKER, Chunker)
AUTH: PortSpec[AuthProvider] = PortSpec(PluginKind.AUTH, AuthProvider)
RATE_LIMITER: PortSpec[RateLimiter] = PortSpec(PluginKind.RATE_LIMITER, RateLimiter)
TOOL: PortSpec[Tool] = PortSpec(PluginKind.TOOL, Tool)
STORAGE: PortSpec[StorageBackend] = PortSpec(PluginKind.STORAGE, StorageBackend)

PORT_BY_KIND: dict[PluginKind, PortSpec[Any]] = {
    spec.kind: spec
    for spec in (LLM, EMBEDDER, VECTOR_STORE, LOADER, CHUNKER, AUTH, RATE_LIMITER, TOOL, STORAGE)
}
"""Every kind's spec; a test asserts it covers all of :class:`PluginKind`."""
