from pypdf import PdfReader

from app.models import ChatResponse
from app.prompts import build_prompt
from app.services.cache import get_cached, set_cache
from app.services.ollama_client import embed, generate
from app.services.vector_store import add_documents, query


def load_pdf(file) -> str:
    reader = PdfReader(file, strict=False)
    text = "\n".join(filter(None, (page.extract_text() for page in reader.pages)))

    if not text.strip():
        raise ValueError("No readable text in PDF")

    return text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def ingest_pdf(file) -> int:
    chunks = chunk_text(load_pdf(file))
    valid_chunks: list[str] = []
    embeddings: list[list[float]] = []

    for chunk in chunks:
        chunk_embedding = embed(chunk)
        if chunk_embedding:
            valid_chunks.append(chunk)
            embeddings.append(chunk_embedding)

    if not embeddings:
        raise ValueError("No valid embeddings generated")

    add_documents(valid_chunks, embeddings)
    return len(valid_chunks)


def hybrid_query(query_text: str, model: str) -> ChatResponse:
    if not query_text.strip():
        return ChatResponse(response="Empty query", model=model)

    cached = get_cached(query_text, model=model)
    if cached:
        return ChatResponse(response=cached, model=model, cached=True)

    query_embedding = embed(query_text)
    if not query_embedding:
        response = generate(query_text, model)
        set_cache(query_text, response, model=model)
        return ChatResponse(response=response, model=model)

    docs = query(query_embedding)
    if not docs or not any(doc.strip() for doc in docs):
        response = generate(query_text, model)
        set_cache(query_text, response, model=model)
        return ChatResponse(response=response, model=model)

    prompt = build_prompt(query_text, "\n".join(docs))
    response = generate(prompt, model)
    set_cache(query_text, response, model=model)
    return ChatResponse(response=response, model=model, sources=docs)
