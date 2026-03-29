import chromadb
import os

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")

client = chromadb.HttpClient(host=CHROMA_HOST, port=8000)

collection = client.get_or_create_collection(name="documents")


def add_documents(texts, embeddings):
    for i, (text, emb) in enumerate(zip(texts, embeddings)):
        collection.add(
            documents=[text],
            embeddings=[emb],
            ids=[f"id_{i}_{hash(text)}"]
        )


def query(query_embedding, n_results=3):
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    return results["documents"][0]