"""
RAG (Retrieval-Augmented Generation) Module
Handles document ingestion and hybrid query processing
"""
from pypdf import PdfReader
from typing import List, BinaryIO
from ollama_client import generate_embedding, generate_response
from vector_store import add_documents, query_documents
from prompts import build_rag_prompt, build_chat_prompt
from cache import get_cached_response, set_cached_response


def extract_text_from_pdf(file: BinaryIO) -> str:
    """
    Extract text from a PDF file
    
    Args:
        file: PDF file object
    
    Returns:
        Extracted text content
    """
    try:
        reader = PdfReader(file, strict=False)
        text = ""
        
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        if not text.strip():
            raise ValueError("No readable text found in PDF")
        
        print(f"✅ Extracted {len(text)} characters from PDF")
        return text
    
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks
    
    Args:
        text: Input text to chunk
        chunk_size: Size of each chunk in characters
        overlap: Number of overlapping characters between chunks
    
    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []
    
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        
        # Only add non-empty chunks
        if chunk.strip():
            chunks.append(chunk.strip())
        
        # Move start position with overlap
        start = end - overlap
    
    print(f"✅ Created {len(chunks)} chunks from text")
    return chunks


def ingest_pdf(file: BinaryIO) -> int:
    """
    Process and index a PDF file for RAG
    
    Args:
        file: PDF file object
    
    Returns:
        Number of chunks successfully indexed
    """
    # Extract text from PDF
    text = extract_text_from_pdf(file)
    
    # Split into chunks
    chunks = chunk_text(text)
    
    if not chunks:
        raise ValueError("No valid chunks created from PDF")
    
    # Generate embeddings for each chunk
    valid_chunks = []
    embeddings = []
    
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)
        
        if embedding:
            valid_chunks.append(chunk)
            embeddings.append(embedding)
        else:
            print(f"⚠️  Skipping chunk {i+1}: embedding failed")
    
    if not embeddings:
        raise ValueError("No valid embeddings generated")
    
    # Add to vector store
    success = add_documents(valid_chunks, embeddings)
    
    if not success:
        raise ValueError("Failed to add documents to vector store")
    
    print(f"✅ Successfully indexed {len(valid_chunks)} chunks")
    return len(valid_chunks)


def hybrid_query(query: str, model: str, use_cache: bool = True) -> str:
    """
    Process a query using hybrid approach (RAG + fallback)
    
    Flow:
    1. Check cache
    2. Generate query embedding
    3. Search vector store
    4. If context found -> RAG
    5. If no context -> Direct LLM
    6. Cache result
    
    Args:
        query: User's question
        model: LLM model to use
        use_cache: Whether to use caching
    
    Returns:
        Generated response
    """
    if not query or not query.strip():
        return "⚠️  Please provide a valid question"
    
    # Check cache first
    if use_cache:
        cached = get_cached_response(query, model)
        if cached:
            return cached
    
    # Generate embedding for the query
    query_embedding = generate_embedding(query)
    
    # Fallback if embedding fails
    if not query_embedding:
        print("⚠️  Embedding failed, using direct LLM")
        prompt = build_chat_prompt(query)
        response = generate_response(prompt, model)
        
        if use_cache:
            set_cached_response(query, response, model)
        
        return response
    
    # Search vector store for relevant documents
    documents = query_documents(query_embedding, n_results=3)
    
    # Use RAG if documents found, otherwise fallback to direct LLM
    if documents and any(doc.strip() for doc in documents):
        print(f"✅ Found {len(documents)} relevant documents, using RAG")
        context = "\n\n".join(documents)
        prompt = build_rag_prompt(query, context)
    else:
        print("⚠️  No relevant documents found, using direct LLM")
        prompt = build_chat_prompt(query)
    
    # Generate response
    response = generate_response(prompt, model)
    
    # Cache the response
    if use_cache:
        set_cached_response(query, response, model)
    
    return response


def hybrid_query_stream(query: str, model: str):
    """
    Stream response using hybrid approach (RAG + fallback) with caching
    
    Args:
        query: User's question
        model: LLM model to use
    
    Yields:
        Text chunks as they arrive
    """
    if not query or not query.strip():
        yield "Please provide a valid question"
        return
    
    # Check cache first
    from cache import get_cached_response, set_cached_response
    cached = get_cached_response(query, model)
    
    if cached:
        print("✅ CACHE HIT - Returning cached response")
        # Stream cached response word by word for consistency
        words = cached.split()
        for word in words:
            yield word + " "
        return
    
    print("❌ CACHE MISS - Generating new response")
    
    # Generate embedding for the query using the same model
    print(f"🔍 Generating embedding with model: {model}")
    query_embedding = generate_embedding(query, model=model)
    
    if not query_embedding:
        print("❌ Failed to generate embedding, using direct LLM")
        prompt = build_chat_prompt(query)
    else:
        print("✅ Embedding generated successfully")
        
        # Search vector store for relevant documents
        print("🔍 Searching vector store...")
        documents = query_documents(query_embedding, n_results=5)
        
        print(f"📊 Retrieved {len(documents)} documents")
        for i, doc in enumerate(documents[:2]):
            print(f"   Doc {i+1} preview: {doc[:100]}...")
        
        # Use RAG if we have any documents
        if documents and len(documents) > 0:
            print(f"✅ Using RAG with {len(documents)} documents")
            context = "\n\n---\n\n".join(documents)
            prompt = build_rag_prompt(query, context)
        else:
            print("⚠️  No documents retrieved, using direct LLM")
            prompt = build_chat_prompt(query)
    
    # Stream response from LLM
    from ollama_client import stream_response
    full_response = ""
    
    for chunk in stream_response(prompt, model):
        full_response += chunk
        yield chunk
    
    # Cache the complete response
    if full_response:
        set_cached_response(query, full_response, model)
        print("✅ Response cached")


def clear_all_documents() -> bool:
    """
    Clear all indexed documents from vector store
    
    Returns:
        True if successful
    """
    from vector_store import clear_collection
    return clear_collection()

# Made with Bob
