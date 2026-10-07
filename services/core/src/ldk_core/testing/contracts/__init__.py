"""One contract suite per port. Subclass the one for your port.

Suite classes are not named ``Test*``, so pytest only collects them through
your subclass, which supplies the fixtures each suite documents.
"""

from ldk_core.testing.contracts.documents import (
    DOCUMENTS,
    ChunkerContract,
    DocumentLoaderContract,
)
from ldk_core.testing.contracts.llm import EmbedderContract, LLMProviderContract
from ldk_core.testing.contracts.platform import (
    AuthProviderContract,
    RateLimiterContract,
    StorageBackendContract,
    ToolContract,
)
from ldk_core.testing.contracts.vector_store import DIMENSION, VectorStoreContract

__all__ = [
    "DIMENSION",
    "DOCUMENTS",
    "AuthProviderContract",
    "ChunkerContract",
    "DocumentLoaderContract",
    "EmbedderContract",
    "LLMProviderContract",
    "RateLimiterContract",
    "StorageBackendContract",
    "ToolContract",
    "VectorStoreContract",
]
