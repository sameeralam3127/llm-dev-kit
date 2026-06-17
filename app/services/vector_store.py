from uuid import uuid4

from app.config import get_settings


settings = get_settings()
client = None
collection = None


def get_collection():
    global client, collection

    if collection is None:
        import chromadb

        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        collection = client.get_or_create_collection(name="documents")

    return collection


def add_documents(texts: list[str], embeddings: list[list[float]]) -> None:
    if not texts or not embeddings:
        raise ValueError("Empty data")

    if len(texts) != len(embeddings):
        raise ValueError("Mismatch texts vs embeddings")

    get_collection().add(
        documents=texts,
        embeddings=embeddings,
        ids=[f"doc_{uuid4().hex}" for _ in texts],
    )


def query(query_embedding: list[float], n_results: int = 3) -> list[str]:
    results = get_collection().query(query_embeddings=[query_embedding], n_results=n_results)
    return results.get("documents", [[]])[0]


def clear_all_documents() -> bool:
    global collection

    try:
        if collection is not None:
            client.delete_collection(name="documents")
            collection = None
        else:
            import chromadb

            active_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
            active_client.delete_collection(name="documents")
        get_collection()
        return True
    except Exception as exc:
        print(f"Vector store clear error: {exc}")
        return False


def get_collection_stats() -> dict:
    try:
        return {"status": "connected", "document_count": get_collection().count()}
    except Exception as exc:
        print(f"Vector store stats error: {exc}")
        return {"status": "offline", "document_count": 0}
