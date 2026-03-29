# LLM Dev Kit

A local-first toolkit for building and testing LLM applications using Ollama, Streamlit, RAG (Retrieval-Augmented Generation), ChromaDB, and Redis.

This project is designed to be simple, reproducible, and developer-friendly. It allows you to run everything locally, upload documents, and query them using a hybrid approach that combines retrieval and direct LLM responses.

---

## Overview

This application provides:

- Local LLM inference using Ollama
- Document-based question answering (RAG)
- Automatic fallback to general LLM responses
- Vector search using ChromaDB
- Response caching using Redis
- Clean Streamlit interface for testing and experimentation

No external APIs are required. Everything runs locally.

---

## Architecture

```
User Input
   ↓
Cache Check (Redis)
   ↓
Embedding (Ollama)
   ↓
Vector Search (ChromaDB)
   ↓
If context found → RAG
Else → Direct LLM
   ↓
Response Cached (Redis)
```

---

## Tech Stack

- Ollama – Local LLM runtime
- Streamlit – Web interface
- ChromaDB – Vector database
- Redis – Caching layer
- PyPDF – PDF parsing

---

## Prerequisites

Install the following:

- Python 3.10 or 3.11
- Docker and Docker Compose
- Ollama (installed locally, not in Docker)

Install Ollama from:
https://ollama.com

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/sameeralam3127/llm-dev-kit.git
cd llm-dev-kit
```

---

### 2. Start Ollama

```bash
ollama serve
```

---

### 3. Pull required models

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

---

### 4. Start services (Redis + Chroma + App)

```bash
docker-compose up --build
```

---

### 5. Open the application

```
http://localhost:8501
```

---

## How It Works

### Chat and RAG (Hybrid Mode)

The system automatically decides how to answer:

- If relevant document context is found → uses RAG
- If no context is found → falls back to direct LLM response

There is no manual mode switching required.

---

### Uploading and Using PDFs

1. Upload a PDF from the sidebar

2. The system will:
   - Extract text
   - Split into chunks
   - Generate embeddings
   - Store in ChromaDB

3. Ask questions related to the document

Example:

```
Summarize this document
What are the key points?
Explain section 2
```

---

### Caching (Redis)

Responses are cached based on:

- User prompt
- Selected model

If the same question is asked again:

- The response is returned instantly from cache
- No LLM call is made

---

## Troubleshooting

### Ollama not responding

Make sure Ollama is running:

```bash
ollama serve
```

---

### Model not found

Check installed models:

```bash
ollama list
```

Pull missing models:

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

---

### Cache not working

Check logs:

```bash
docker-compose logs -f
```

Look for:

```
CACHE HIT
CACHE MISS
```

---

### No results from PDF

- Ensure the PDF contains selectable text (not scanned images)
- Re-upload the file

---

## Notes

- This is a local development toolkit, not a production deployment
- No external APIs or cloud services are used
- Designed for experimentation and learning

---

## Future Improvements

- Streaming responses
- Source visibility (show retrieved chunks)
- Multi-document support
- Advanced retrieval ranking

---

## License

MIT
