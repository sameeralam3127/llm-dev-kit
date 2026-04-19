# LLM Dev Kit

A local-first enterprise toolkit for building and testing LLM applications using Ollama, Streamlit, RAG (Retrieval-Augmented Generation), ChromaDB, and Redis.

This project is designed to be simple, reproducible, and developer-friendly. It allows you to run everything locally, upload documents, and query them using a hybrid approach that combines retrieval and direct LLM responses.

---

## Overview

This application provides:

- Local LLM inference using Ollama
- Document-based question answering (RAG)
- Automatic fallback to general LLM responses
- Vector search using ChromaDB
- Response caching using Redis
- Enterprise Streamlit interface with streaming responses
- Persistent chat history and document storage

No external APIs are required. Everything runs locally.

---

## Architecture

```
User Input
   ↓
Cache Check (Redis)
   ↓
Embedding Generation (llama3.1:8b)
   ↓
Vector Search (ChromaDB)
   ↓
If documents found → RAG with context
Else → Direct LLM
   ↓
Streaming Response
   ↓
Response Cached (Redis)
   ↓
History Saved (Persistent)
```

---

## Tech Stack

- **Ollama** – Local LLM runtime
- **Streamlit** – Enterprise web interface
- **ChromaDB** – Vector database for document embeddings
- **Redis** – Response caching layer
- **PyPDF** – PDF document parsing
- **Docker** – Containerized deployment

---

## Prerequisites

Install the following:

- Python 3.11
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

### 3. Pull required model

```bash
ollama pull llama3.1:8b
```

Note: This model is used for both chat and embeddings.

---

### 4. Start services (Redis + ChromaDB + Streamlit)

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

### Model Selection

- No default model is selected
- User must explicitly choose a model from the dropdown
- Recommended: llama3.1:8b

### Chat and RAG (Hybrid Mode)

The system automatically decides how to answer:

- If relevant document context is found → uses RAG
- If no context is found → falls back to direct LLM response

There is no manual mode switching required.

### Streaming Responses

- Responses stream token-by-token for faster perceived performance
- Processing indicator shows while generating embeddings
- Real-time display with cursor animation

---

## Uploading and Using PDFs

1. Select a model from the sidebar dropdown

2. Upload a PDF from the sidebar

3. The system will:
   - Extract text from the PDF
   - Split into chunks (500 characters with 50 character overlap)
   - Generate embeddings using llama3.1:8b
   - Store in ChromaDB vector database

4. Ask questions related to the document

Example queries:

```
Summarize this document
What are the key points?
Explain section 2
What does the document say about [topic]?
```

---

## Caching (Redis)

Responses are cached based on:

- User prompt
- Selected model

If the same question is asked again:

- The response is returned instantly from cache
- No LLM call is made
- Cache keys metric increments

---

## Persistent Storage

### Chat History

- Saved to `/app/data/chat_history.json`
- Persists across container restarts
- Export functionality available in sidebar

### Uploaded Documents

- Stored in `/app/data/uploads/`
- Vector embeddings in ChromaDB volume

### Docker Volumes

- `app_data` - Chat history and uploads
- `redis_data` - Cache persistence
- `chroma_data` - Vector store persistence

---

## Features

### Enterprise UI

- Professional design without emojis
- Clean, consistent chat interface
- Model selection required before chatting
- System status metrics in sidebar

### Performance

- Streaming responses for faster interaction
- Redis caching for instant repeated queries
- Optimized PDF processing
- Efficient vector search

### Reliability

- Automatic service health checks
- Persistent data storage
- Comprehensive error handling
- Detailed logging for debugging

---

## Troubleshooting

### Ollama not responding

Make sure Ollama is running:

```bash
ollama serve
```

Check if it's accessible:

```bash
curl http://localhost:11434/api/tags
```

---

### Model not found

Check installed models:

```bash
ollama list
```

Pull the required model:

```bash
ollama pull llama3.1:8b
```

---

### Cache not working

Check Docker logs:

```bash
docker-compose logs -f app
```

Look for:

```
CACHE HIT
CACHE MISS
CACHE SET
```

---

### RAG not using documents

Check logs for:

```
Using RAG with X documents
Retrieved X documents
```

If you see "No documents retrieved", ensure:

- PDF was successfully uploaded
- Model is selected
- Documents metric shows count > 0

---

### No results from PDF

- Ensure the PDF contains selectable text (not scanned images)
- Check that documents were indexed (see Documents metric)
- Try re-uploading the file

---

## Configuration

### Environment Variables

Create a `.env` file (see `.env.example`):

```bash
OLLAMA_HOST=http://localhost:11434
REDIS_HOST=localhost
REDIS_PORT=6379
CHROMA_HOST=localhost
CHROMA_PORT=8000
CACHE_TTL=3600
```

---

## Development

### Running Locally (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start Ollama
ollama serve

# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Start ChromaDB
docker run -d -p 8000:8000 chromadb/chroma

# Run Streamlit
streamlit run app/main.py
```

---

## Notes

- This is a local development toolkit, not a production deployment
- No external APIs or cloud services are used
- Designed for experimentation and learning
- All data stays on your machine

---

## Future Improvements

- Multi-document support with document management
- Advanced retrieval ranking algorithms
- Source citation in responses
- Conversation memory and context
- Model fine-tuning capabilities

---

## License

MIT

---

## Support

For issues and questions:

- Check the logs: `docker-compose logs -f app`
- Verify services: `docker-compose ps`
- Review this README for troubleshooting steps
