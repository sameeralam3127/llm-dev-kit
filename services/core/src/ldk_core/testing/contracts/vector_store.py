"""Contract suite for :class:`VectorStore`."""

from __future__ import annotations

import pytest

from ldk_core.ports import ChunkRecord, SearchScope, VectorStore
from ldk_core.testing.contracts._util import REGISTRY_NAME, run, unimplemented

DIMENSION = 4
"""Vector length the suite uses; ``store`` must accept it."""


def _vec(*xs: float) -> list[float]:
    """A ``DIMENSION``-long vector, zero-padded."""
    return [*xs, *([0.0] * (DIMENSION - len(xs)))]


def _chunk(cid: str, doc: str, embedding: list[float], page: int | None = None) -> ChunkRecord:
    """A record whose text names its id, so results are easy to read."""
    return ChunkRecord(
        id=cid, document_id=doc, text=f"text of {cid}", embedding=embedding, page=page
    )


def _scope(*collections: str, user: str | None = "contract-user") -> SearchScope:
    """A scope over ``collections``."""
    return SearchScope(collection_ids=frozenset(collections), user_id=user)


class VectorStoreContract:
    """Every :class:`VectorStore` must pass this.

    Fixtures to provide:
        store: A fresh, empty store accepting :data:`DIMENSION`-long vectors,
            in which ``scope.user_id`` may read collections ``"a"`` and
            ``"b"`` (grant them in the fixture if the store checks grants).
    """

    @pytest.fixture
    def store(self) -> VectorStore:
        """The implementation under test, empty."""
        unimplemented("store")

    def _seed(self, store: VectorStore) -> None:
        run(
            store.upsert(
                "a",
                [
                    _chunk("a1", "doc-1", _vec(1, 0), page=1),
                    _chunk("a2", "doc-1", _vec(0.9, 0.1), page=2),
                    _chunk("a3", "doc-2", _vec(0, 1)),
                ],
            )
        )
        run(store.upsert("b", [_chunk("b1", "doc-3", _vec(1, 0))]))

    def test_satisfies_the_protocol(self, store: VectorStore) -> None:
        """The runtime check the registry applies passes."""
        assert isinstance(store, VectorStore)
        assert REGISTRY_NAME.fullmatch(store.name)

    def test_nearest_first_and_top_k(self, store: VectorStore) -> None:
        """Results are ordered by descending score and capped at ``top_k``."""
        self._seed(store)
        results = run(store.search(_vec(1, 0), scope=_scope("a"), top_k=2))
        assert [r.chunk_id for r in results] == ["a1", "a2"]
        assert results[0].score >= results[1].score

    def test_fields_round_trip(self, store: VectorStore) -> None:
        """Document id, text and page come back as stored, for citations."""
        self._seed(store)
        (top,) = run(store.search(_vec(1, 0), scope=_scope("a"), top_k=1))
        assert (top.document_id, top.text, top.page) == ("doc-1", "text of a1", 1)

    def test_scope_excludes_other_collections(self, store: VectorStore) -> None:
        """A chunk outside the scope is never returned, however similar."""
        self._seed(store)
        results = run(store.search(_vec(1, 0), scope=_scope("a"), top_k=10))
        assert "b1" not in {r.chunk_id for r in results}
        both = run(store.search(_vec(1, 0), scope=_scope("a", "b"), top_k=10))
        assert "b1" in {r.chunk_id for r in both}

    def test_empty_scope_matches_nothing(self, store: VectorStore) -> None:
        """No collections means no results, not every result."""
        self._seed(store)
        assert run(store.search(_vec(1, 0), scope=_scope(), top_k=10)) == []

    def test_upsert_replaces_by_id(self, store: VectorStore) -> None:
        """Re-upserting an id replaces the chunk instead of duplicating it."""
        self._seed(store)
        replacement = ChunkRecord("a1", "doc-1", "rewritten", _vec(1, 0), page=1)
        run(store.upsert("a", [replacement]))
        assert run(store.count("a")) == 3
        (top,) = run(store.search(_vec(1, 0), scope=_scope("a"), top_k=1))
        assert top.text == "rewritten"

    def test_counts(self, store: VectorStore) -> None:
        """Per collection and in total."""
        assert run(store.count()) == 0
        self._seed(store)
        assert (run(store.count("a")), run(store.count("b")), run(store.count())) == (3, 1, 4)

    def test_delete_document(self, store: VectorStore) -> None:
        """Removes only that document's chunks and reports how many."""
        self._seed(store)
        assert run(store.delete_document("a", "doc-1")) == 2
        assert run(store.count("a")) == 1
        assert run(store.delete_document("a", "doc-1")) == 0

    def test_clear_one_collection(self, store: VectorStore) -> None:
        """Clearing ``a`` leaves ``b`` untouched."""
        self._seed(store)
        run(store.clear("a"))
        assert (run(store.count("a")), run(store.count("b"))) == (0, 1)
