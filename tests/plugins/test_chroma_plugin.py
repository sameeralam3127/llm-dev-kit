"""vector_store.chroma.

The contract suite needs a real Chroma server: set LDK_TEST_CHROMA_HOST (and
optionally LDK_TEST_CHROMA_PORT). CI runs one as a service container; locally
`docker run -p 8000:8000 chromadb/chroma:1.5.9` works.
"""

import asyncio
import os
import time
import uuid

import pytest

from ldk_core.errors import ErrorCode, ServiceError
from ldk_core.ports import ChunkRecord, SearchScope
from ldk_core.testing.contracts import VectorStoreContract
from ldk_plugin_chroma import ChromaVectorStore
from ldk_plugin_chroma.store import _results

CHROMA_HOST = os.environ.get("LDK_TEST_CHROMA_HOST")
CHROMA_PORT = int(os.environ.get("LDK_TEST_CHROMA_PORT", "8000"))
needs_chroma = pytest.mark.skipif(not CHROMA_HOST, reason="set LDK_TEST_CHROMA_HOST")


def _wait_for_chroma(store: ChromaVectorStore) -> None:
    deadline = time.monotonic() + 30
    while True:
        try:
            store._get_client().heartbeat()
            return
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


@pytest.fixture
def live_store():
    assert CHROMA_HOST
    # A unique prefix per test keeps runs independent and leaves no state.
    store = ChromaVectorStore(
        CHROMA_HOST, CHROMA_PORT, collection_prefix=f"ldk-test-{uuid.uuid4().hex[:8]}-"
    )
    _wait_for_chroma(store)
    yield store
    client = store._get_client()
    for collection in client.list_collections():
        if collection.name.startswith(store.prefix):
            client.delete_collection(name=collection.name)


@needs_chroma
class TestChromaContract(VectorStoreContract):
    @pytest.fixture
    def store(self, live_store: ChromaVectorStore) -> ChromaVectorStore:
        return live_store


@needs_chroma
def test_legacy_rows_without_metadata_are_still_searchable(live_store: ChromaVectorStore) -> None:
    # Pre-v2 ingests wrote documents and embeddings only.
    collection = live_store._collection("documents")
    collection.add(ids=["doc_old"], documents=["old text"], embeddings=[[1.0, 0.0, 0.0, 0.0]])
    (hit,) = asyncio.run(
        live_store.search(
            [1.0, 0.0, 0.0, 0.0], scope=SearchScope(frozenset({"documents"})), top_k=3
        )
    )
    assert (hit.text, hit.document_id, hit.page) == ("old text", "", None)


def test_results_parsing_handles_missing_metadata() -> None:
    res = {
        "ids": [["a", "b"]],
        "documents": [["first", None]],
        "metadatas": [[{"document_id": "d1", "page": 2, "filename": "x.pdf"}, None]],
        "distances": [[0.0, 1.0]],
    }
    first, second = _results(res)
    assert (first.document_id, first.page, first.metadata, first.score) == (
        "d1",
        2,
        {"filename": "x.pdf"},
        1.0,
    )
    assert (second.text, second.document_id, second.page, second.score) == ("", "", None, 0.5)


class _BrokenClient:
    def get_or_create_collection(self, name: str):
        raise ConnectionError("Could not connect to a Chroma server")


def test_outages_become_upstream_unavailable() -> None:
    store = ChromaVectorStore("chroma.test", client=_BrokenClient())
    with pytest.raises(ServiceError) as info:
        asyncio.run(store.count("documents"))
    assert info.value.code is ErrorCode.UPSTREAM_UNAVAILABLE
    assert "Could not connect" in info.value.message


def test_empty_upsert_and_empty_scope_touch_nothing() -> None:
    store = ChromaVectorStore("chroma.test", client=_BrokenClient())
    asyncio.run(store.upsert("documents", []))
    assert asyncio.run(store.search([1.0], scope=SearchScope(frozenset()), top_k=3)) == []


def test_none_metadata_values_are_dropped() -> None:
    from ldk_plugin_chroma.store import _metadata

    record = ChunkRecord("c", "d", "t", [0.0], page=None, metadata={"filename": None, "k": 1})
    assert _metadata(record) == {"k": 1, "document_id": "d"}
