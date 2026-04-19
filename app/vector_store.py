"""
Vector Store Module
Handles document storage and retrieval using ChromaDB
"""
import chromadb
import os
from typing import List, Optional
from chromadb.config import Settings

# Configuration
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", 8000))
COLLECTION_NAME = "documents"

# ChromaDB client and collection
_chroma_client: Optional[chromadb.HttpClient] = None
_collection = None


def get_chroma_client() -> Optional[chromadb.HttpClient]:
    """
    Get or create ChromaDB client
    
    Returns:
        ChromaDB client instance or None if connection fails
    """
    global _chroma_client
    
    if _chroma_client is not None:
        return _chroma_client
    
    try:
        _chroma_client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        # Test connection
        _chroma_client.heartbeat()
        print(f"✅ ChromaDB connected at {CHROMA_HOST}:{CHROMA_PORT}")
        return _chroma_client
    except Exception as e:
        print(f"⚠️  ChromaDB not available: {e}")
        print("💡 Vector search will be disabled")
        return None


def get_collection():
    """
    Get or create the documents collection
    
    Returns:
        ChromaDB collection instance
    """
    global _collection
    
    if _collection is not None:
        return _collection
    
    client = get_chroma_client()
    if not client:
        return None
    
    try:
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Document embeddings for RAG"}
        )
        print(f"✅ Collection '{COLLECTION_NAME}' ready")
        return _collection
    except Exception as e:
        print(f"❌ Failed to get collection: {e}")
        return None


def add_documents(
    texts: List[str],
    embeddings: List[List[float]],
    metadata: Optional[List[dict]] = None
) -> bool:
    """
    Add documents to the vector store
    
    Args:
        texts: List of document texts
        embeddings: List of embedding vectors
        metadata: Optional metadata for each document
    
    Returns:
        True if successful, False otherwise
    """
    collection = get_collection()
    
    if not collection:
        print("❌ Collection not available")
        return False
    
    if not texts or not embeddings:
        print("❌ Empty texts or embeddings")
        return False
    
    if len(texts) != len(embeddings):
        print("❌ Mismatch: texts and embeddings must have same length")
        return False
    
    try:
        # Generate unique IDs for documents
        ids = [f"doc_{i}_{hash(text)}" for i, text in enumerate(texts)]
        
        # Prepare metadata
        if metadata is None:
            metadata = [{"index": i} for i in range(len(texts))]
        
        # Add to collection
        collection.add(
            documents=texts,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadata
        )
        
        print(f"✅ Added {len(texts)} documents to vector store")
        return True
    
    except Exception as e:
        print(f"❌ Failed to add documents: {e}")
        return False


def query_documents(
    query_embedding: List[float],
    n_results: int = 3,
    min_similarity: float = 0.0
) -> List[str]:
    """
    Query the vector store for similar documents
    
    Args:
        query_embedding: Query embedding vector
        n_results: Number of results to return
        min_similarity: Minimum similarity threshold (0.0 to 1.0)
    
    Returns:
        List of matching document texts
    """
    collection = get_collection()
    
    if not collection:
        print("❌ Collection not available")
        return []
    
    if not query_embedding:
        print("❌ Empty query embedding")
        return []
    
    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        # Filter by similarity threshold
        filtered_docs = []
        for doc, dist in zip(documents, distances):
            # Convert distance to similarity (lower distance = higher similarity)
            similarity = 1.0 - dist
            if similarity >= min_similarity:
                filtered_docs.append(doc)
        
        if filtered_docs:
            print(f"✅ Found {len(filtered_docs)} matching documents")
        else:
            print("❌ No matching documents found")
        
        return filtered_docs
    
    except Exception as e:
        print(f"❌ Query failed: {e}")
        return []


def clear_collection() -> bool:
    """
    Clear all documents from the collection
    
    Returns:
        True if successful, False otherwise
    """
    client = get_chroma_client()
    
    if not client:
        return False
    
    try:
        client.delete_collection(name=COLLECTION_NAME)
        global _collection
        _collection = None
        print(f"✅ Collection '{COLLECTION_NAME}' cleared")
        return True
    except Exception as e:
        print(f"❌ Failed to clear collection: {e}")
        return False


def get_collection_stats() -> dict:
    """
    Get collection statistics
    
    Returns:
        Dictionary with collection stats
    """
    collection = get_collection()
    
    if not collection:
        return {"status": "unavailable"}
    
    try:
        count = collection.count()
        return {
            "status": "connected",
            "name": COLLECTION_NAME,
            "document_count": count
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Made with Bob
