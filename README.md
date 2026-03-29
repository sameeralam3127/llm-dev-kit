# LLM Dev Kit

A simple, local-first toolkit to build and experiment with LLM applications using **Ollama**, **Streamlit**, **RAG (PDF-based retrieval)**, **ChromaDB**, and **Redis caching** — all with a clean Docker setup.

---

## What is this?

This project is designed as a **developer-friendly playground** for working with local LLMs.

You can:

- Chat with local models (via Ollama)
- Upload PDFs and “train” them (RAG)
- Ask questions based on your documents
- Experiment with prompts and models
- Get faster responses using Redis caching

Everything runs locally. No APIs. No cloud dependencies.

---

## Tech Stack

- **Ollama** → Runs LLMs locally (llama3, mistral, etc.)
- **Streamlit** → Simple and clean chat UI
- **ChromaDB** → Vector database for RAG
- **Redis** → Caching for faster responses
- **Docker** → Runs services (except Ollama)

---

## Prerequisites

Make sure you have:

- Docker & Docker Compose installed
- Ollama installed locally → [https://ollama.com](https://ollama.com)

---

## Setup (very simple)

### 1. Clone the repo

```bash
git clone https://github.com/sameeralam3127/llm-dev-kit.git
cd llm-dev-kit
```

---

### 2. Install & start Ollama

```bash
ollama serve
```

Pull required models:

```bash
ollama pull llama3
ollama pull mistral
ollama pull nomic-embed-text
```

---

### 3. Start the app

```bash
docker-compose -f docker/docker-compose.yml up --build
```

---

### 4. Open in browser

```
http://localhost:8501
```

---

## How to Use

### 👉 Chat Mode

- Select **Chat**
- Choose a model (llama3 / mistral)
- Start asking questions

---

### RAG Mode (PDF “training”)

This is where things get interesting.

#### Step 1: Upload a PDF

Use the sidebar uploader.

#### Step 2: What happens internally?

When you upload a PDF:

1. The PDF is read and converted to text
2. Text is split into smaller chunks
3. Each chunk is converted into embeddings
4. Embeddings are stored in ChromaDB

👉 This is NOT training the model
👉 This is called **RAG (Retrieval-Augmented Generation)**

---

#### Step 3: Ask questions

Switch to **RAG mode** and ask:

```
What is this document about?
```

The system will:

1. Convert your question into an embedding
2. Retrieve relevant chunks from the database
3. Send them as context to the LLM
4. Generate an answer based on your PDF

---

## ⚡ Why Redis?

LLM responses can be slow.

Redis helps by:

- Caching previous responses
- Avoiding repeated computation
- Making repeated queries instant

👉 Ask the same question twice — second time will be faster.

---

## Why Ollama?

- Runs models **locally**
- No API keys required
- Supports multiple models
- Privacy-friendly

---

## Why Streamlit?

- Extremely fast to build UI
- Perfect for prototyping LLM apps
- Built-in chat components
- Minimal frontend effort

---

## Why ChromaDB?

- Simple local vector database
- Stores embeddings for RAG
- Easy to integrate
- No complex setup

---

## Workflow Summary

```text
PDF → chunk → embeddings → ChromaDB
User Query → embedding → similarity search
→ context → LLM (Ollama) → answer
```

---

## 🧪 Example Queries

- “Summarize this document”
- “What are the key points?”
- “Explain section 2”
- “Give me a short summary”

---

## 🧯 Troubleshooting

### Ollama not responding

Make sure:

```bash
ollama serve
```

---

### RAG not working

- Ensure PDF was uploaded
- Ensure embeddings model is pulled:

```bash
ollama pull nomic-embed-text
```

---

### Docker issues

Check logs:

```bash
docker-compose -f docker/docker-compose.yml logs app
```

---

## 📌 Notes

- This is a **local-first dev toolkit**, not production-ready SaaS
- No external APIs are used
- You can extend this with LangChain, agents, or tools

---

## ⭐ Future Improvements

- Streaming responses
- Source citations in UI
- Multi-document support
- Better prompt controls

---

## License

MIT
