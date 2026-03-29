from pypdf import PdfReader
from app.ollama_client import embed, generate
from app.vector_store import add_documents, query
from app.prompts import build_prompt
from app.cache import get_cached, set_cache


def load_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


def chunk_text(text, chunk_size=500):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


def ingest_pdf(file):
    text = load_pdf(file)
    chunks = chunk_text(text)

    embeddings = [embed(chunk) for chunk in chunks]

    add_documents(chunks, embeddings)

    return len(chunks)


def rag_query(query_text, model="llama3"):
    # cache check
    cached = get_cached(query_text)
    if cached:
        return cached

    query_embedding = embed(query_text)

    docs = query(query_embedding)

    context = "\n".join(docs)

    prompt = build_prompt(query_text, context)

    response = generate(prompt, model=model)

    set_cache(query_text, response)

    return response