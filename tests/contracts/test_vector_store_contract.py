"""Reference in-memory vector store, proving the suite runs and passes."""

import pytest
from memory_store import MemoryVectorStore

from ldk_core.testing.contracts import VectorStoreContract


class TestMemoryVectorStore(VectorStoreContract):
    @pytest.fixture
    def store(self) -> MemoryVectorStore:
        return MemoryVectorStore()
