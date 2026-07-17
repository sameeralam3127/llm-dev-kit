from rag_service.pdf import chunk_text


def test_chunk_text_uses_overlap():
    chunks = chunk_text("abcdefghij", chunk_size=4, overlap=1)

    assert chunks == ["abcd", "defg", "ghij", "j"]


def test_chunk_text_rejects_invalid_overlap():
    try:
        chunk_text("abc", chunk_size=3, overlap=3)
    except ValueError as exc:
        assert "overlap" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
