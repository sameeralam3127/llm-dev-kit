from uuid import uuid4


class ChromaStore:
    def __init__(self, host: str, port: int, collection_name: str = "documents") -> None:
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb

            self._client = chromadb.HttpClient(host=self.host, port=self.port)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name
            )
        return self._collection

    def add(self, texts: list[str], embeddings: list[list[float]]) -> None:
        if not texts or not embeddings:
            raise ValueError("Empty data")
        if len(texts) != len(embeddings):
            raise ValueError("Mismatch texts vs embeddings")

        self._get_collection().add(
            documents=texts,
            embeddings=embeddings,
            ids=[f"doc_{uuid4().hex}" for _ in texts],
        )

    def query(self, query_embedding: list[float], n_results: int = 3) -> list[str]:
        results = self._get_collection().query(
            query_embeddings=[query_embedding], n_results=n_results
        )
        return results.get("documents", [[]])[0]

    def count(self) -> int:
        return self._get_collection().count()

    def clear(self) -> bool:
        try:
            self._get_collection()
            self._client.delete_collection(name=self.collection_name)
            self._collection = None
            self._get_collection()
            return True
        except Exception:
            return False
