"""The nine ports: every swappable capability, as a structural interface.

Consumers depend on these protocols and receive implementations from the
plugin registry; no consumer imports an implementation module. Each port is
``runtime_checkable`` so the registry can reject an object that does not even
have the right methods, though full conformance is what the contract suites
in ``tests/contracts`` prove.
"""

from ldk_core.ports.auth import AuthProvider, Principal, PrincipalKind
from ldk_core.ports.chunker import Chunker, TextChunk
from ldk_core.ports.embedding import Embedder
from ldk_core.ports.llm import ChatMessage, CompletionRequest, LLMProvider, Role
from ldk_core.ports.loader import DocumentLoader, LoadedDocument, Page
from ldk_core.ports.rate_limit import RateLimitDecision, RateLimiter
from ldk_core.ports.storage import StorageBackend, StoredObject
from ldk_core.ports.tool import Tool
from ldk_core.ports.vector_store import ChunkRecord, SearchResult, SearchScope, VectorStore

__all__ = [
    "AuthProvider",
    "ChatMessage",
    "ChunkRecord",
    "Chunker",
    "CompletionRequest",
    "DocumentLoader",
    "Embedder",
    "LLMProvider",
    "LoadedDocument",
    "Page",
    "Principal",
    "PrincipalKind",
    "RateLimitDecision",
    "RateLimiter",
    "Role",
    "SearchResult",
    "SearchScope",
    "StorageBackend",
    "StoredObject",
    "TextChunk",
    "Tool",
    "VectorStore",
]
