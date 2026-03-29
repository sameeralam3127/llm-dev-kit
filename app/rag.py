from pypdf import PdfReader
from ollama_client import embed, generate
from vector_store import add_documents, query
from prompts import build_prompt
from cache import get_cached, set_cache


# ------------------ PDF ------------------

def load_pdf(file):
    reader = PdfReader(file, strict=False)
    text = ""

    for page in reader.pages:
        t = page.extract_text()
        if t:
            text += t + "\n"

    if not text.strip():
        raise ValueError("No readable text in PDF")

    return text


def chunk_text(text, chunk_size=500):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


# ------------------ INGEST ------------------

def ingest_pdf(file):
    text = load_pdf(file)
    chunks = chunk_text(text)

    valid_chunks = []
    embeddings = []

    for chunk in chunks:
        emb = embed(chunk)

        if emb:
            valid_chunks.append(chunk)
            embeddings.append(emb)
        else:
            print("Skipping invalid chunk")

    if not embeddings:
        raise ValueError("No valid embeddings generated")

    print(f"Indexed {len(embeddings)} chunks")

    add_documents(valid_chunks, embeddings)

    return len(valid_chunks)


# ------------------ HYBRID QUERY (FIXED CACHE) ------------------

def hybrid_query(query_text, model):
    if not query_text.strip():
        return "Empty query"

    # -------- CACHE CHECK --------
    cached = get_cached(query_text, model=model)

    if cached:
        print("CACHE HIT")
        return cached

    print("CACHE MISS")

    # -------- EMBEDDING --------
    query_embedding = embed(query_text)

    # -------- FALLBACK (NO EMBEDDING) --------
    if not query_embedding:
        response = generate(query_text, model)
        set_cache(query_text, response, model=model)
        return response

    # -------- RETRIEVE --------
    docs = query(query_embedding)

    # -------- FALLBACK (NO DOCS) --------
    if not docs or not any(d.strip() for d in docs):
        response = generate(query_text, model)
        set_cache(query_text, response, model=model)
        return response

    # -------- RAG FLOW --------
    context = "\n".join(docs)
    prompt = build_prompt(query_text, context)

    response = generate(prompt, model)

    # IMPORTANT: do NOT pass context here
    set_cache(query_text, response, model=model)

    return response