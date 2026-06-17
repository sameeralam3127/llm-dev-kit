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
