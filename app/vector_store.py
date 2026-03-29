import chromadb
import os

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")

client = chromadb.HttpClient(host=CHROMA_HOST, port=8000)
collection = client.get_or_create_collection(name="documents")


def add_documents(texts, embeddings):
    if not texts or not embeddings:
        raise ValueError("Empty data")

    if len(texts) != len(embeddings):
        raise ValueError("Mismatch texts vs embeddings")

    collection.add(
        documents=texts,
        embeddings=embeddings,
        ids=[f"id_{i}" for i in range(len(texts))]
    )


def query(query_embedding, n_results=3):
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )

    return results.get("documents", [[]])[0]