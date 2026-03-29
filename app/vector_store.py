def embed(text):
    res = requests.post(
        f"{OLLAMA_HOST}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text}
    )
    return res.json()["embedding"]