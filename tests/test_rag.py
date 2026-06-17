from app.services import rag


def test_chunk_text_uses_overlap():
    chunks = rag.chunk_text("abcdefghij", chunk_size=4, overlap=1)

    assert chunks == ["abcd", "defg", "ghij", "j"]


def test_chunk_text_rejects_invalid_overlap():
    try:
        rag.chunk_text("abc", chunk_size=3, overlap=3)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_hybrid_query_returns_cached_response(monkeypatch):
    monkeypatch.setattr(rag, "get_cached", lambda prompt, model=None: "cached answer")

    result = rag.hybrid_query("hello", model="llama3.1")

    assert result.response == "cached answer"
    assert result.cached is True


def test_hybrid_query_falls_back_when_embedding_missing(monkeypatch):
    monkeypatch.setattr(rag, "get_cached", lambda prompt, model=None: None)
    monkeypatch.setattr(rag, "embed", lambda text: None)
    monkeypatch.setattr(rag, "generate", lambda prompt, model: "generated")
    monkeypatch.setattr(rag, "set_cache", lambda prompt, response, model=None: None)

    result = rag.hybrid_query("hello", model="llama3.1")

    assert result.response == "generated"
    assert result.sources == []


def test_hybrid_query_uses_retrieved_context(monkeypatch):
    seen = {}

    monkeypatch.setattr(rag, "get_cached", lambda prompt, model=None: None)
    monkeypatch.setattr(rag, "embed", lambda text: [0.1, 0.2])
    monkeypatch.setattr(rag, "query", lambda embedding: ["doc context"])
    monkeypatch.setattr(rag, "set_cache", lambda prompt, response, model=None: None)

    def fake_generate(prompt, model):
        seen["prompt"] = prompt
        return "rag answer"

    monkeypatch.setattr(rag, "generate", fake_generate)

    result = rag.hybrid_query("hello", model="llama3.1")

    assert result.response == "rag answer"
    assert result.sources == ["doc context"]
    assert "doc context" in seen["prompt"]
