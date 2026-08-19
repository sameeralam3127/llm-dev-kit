# Setup Guide

A step-by-step walkthrough for getting the stack running, ingesting your own
documents, and diagnosing the most common ways it breaks. For a high-level
overview see [../README.md](../README.md); for request-flow diagrams see
[../ARCHITECTURE.md](../ARCHITECTURE.md).

## Prerequisites

- Docker + Docker Compose
- [Ollama](https://ollama.com) installed on the host (or use the `ollama`
  compose profile to run it in a container instead — CPU-only on macOS)
- Optional: an OpenAI and/or Anthropic API key, if you want cloud models

## 1. Pull the local models

```bash
ollama serve
ollama pull llama3.1
ollama pull nomic-embed-text
```

`nomic-embed-text` is required even if you only ever use cloud chat models —
embeddings always run locally.

## 2. Configure environment

```bash
cp .env.example .env
```

Everything works fully offline with the defaults. The sections in `.env` map
to:

| Section | Purpose |
| --- | --- |
| Offline LLM | `OLLAMA_HOST`, default chat/embedding models |
| Cloud providers | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` — leave blank to stay offline |
| Service URLs | Only used when running a service outside Docker |
| Cache | Redis URL + response cache TTL |
| Vector store | Chroma (PDFs) connection info |

## 3. Start the stack

```bash
docker compose up --build
```

Or detached:

```bash
docker compose up -d --build
```

Verify everything is healthy:

```bash
docker compose ps
curl http://localhost:8080/api/rag/health
curl http://localhost:8080/api/llm/health
```

`nginx` is the **only** published port. If `docker compose ps` shows services
as `Exited`, nothing is listening on `:8080` and the whole UI — not just
RAG — will be unreachable; see [Troubleshooting](#troubleshooting).

## 4. Open the chat UI

Go to **http://localhost:8080** — the built-in chat UI loads instantly (a
React + Vite app compiled to static files inside the nginx image; no
account, no frontend container). In the toolbar:

- **Provider** — Local (Ollama) by default; switch to OpenAI, Gemini or
  Anthropic and paste an API key (kept in your browser's localStorage, sent
  per-request, never stored server-side).
- **Model** — populated from `/api/llm/models` (live Ollama models plus
  curated cloud models).
- Every answer is RAG-augmented over whatever you've indexed; responses
  stream token-by-token, cached answers return instantly with a ⚡ badge, and
  retrieved source snippets are shown under each reply.

## 5. Index a PDF

Click the **📎 paperclip** in the message bar (or drag a PDF anywhere onto
the page) — the file is chunked, embedded locally, and indexed into
ChromaDB, with a confirmation note in the chat thread. Or upload via the
API:

```bash
curl -X POST http://localhost:8080/api/rag/ingest/pdf -F "file=@mydoc.pdf"
# {"chunks": 12}
```

Then just chat — relevant chunks are retrieved automatically. Useful checks:

```bash
# how many chunks are currently indexed
curl http://localhost:8080/api/rag/documents/stats

# wipe the PDF index
curl -X POST http://localhost:8080/api/rag/documents/clear
```

The PDF must contain selectable text — scanned image pages produce zero
chunks and a 400 response.

## 6. Cloud models (optional)

Cloud calls are routed through LiteLLM. Set `OPENAI_API_KEY`,
`GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY` in `.env` (server-wide), pass
`api_key` per request to `/api/rag/chat`, or just pick the provider in the
chat UI and paste your key there. See the README's
[Cloud LLMs section](../README.md#cloud-llms--bring-your-own-api-key) for
details.

## Stopping and restarting

```bash
docker compose down      # stop and remove containers
docker compose up -d     # bring the stack back up
```

All services use `restart: unless-stopped`, so the Docker daemon restarting
normally brings them back automatically. However, a host sleep/wake cycle,
Docker Desktop restarting, or resource pressure can still kill every
container in the stack at once (nginx included) without anything restarting
them. If `localhost:8080` stops responding, that's the first thing to check
— see [Troubleshooting](#troubleshooting).

## Local development (outside Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e services/devkit_common -e services/llm_service -e services/rag_service
uvicorn llm_service.main:app --reload --port 8010
uvicorn rag_service.main:app --reload --port 8020
```

Use `.env.example` as a starting point and set `LLM_SERVICE_URL=http://localhost:8010`.

## Running tests

```bash
pip install -r requirements-dev.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

## Scaling rag-service

`rag-service` runs 2 replicas by default (`deploy.replicas` in
`docker-compose.yml`); Nginx round-robins across them via Docker's embedded
DNS. To change the replica count at runtime:

```bash
docker compose up -d --scale rag-service=4
docker compose restart nginx   # re-resolve upstream IPs
```

## Troubleshooting

- **Nothing loads at `localhost:8080` / "RAG option" missing entirely** —
  run `docker compose ps`. If containers show `Exited`, the stack isn't
  running (Docker Desktop restart, host sleep, or a manual `down`/`stop` are
  the usual causes) — bring it back with `docker compose up -d` and re-check
  `docker compose ps` for `healthy` status.
- **"no local models found" in the model picker** — check Ollama is running
  (`ollama list`) and reachable from Docker; the connection URL is
  `http://host.docker.internal:11434` by default.
- **Cloud model errors** — `401` means no/invalid API key: set it in `.env`
  or pass `api_key` per request.
- **PDF retrieval returns nothing** — the PDF must contain selectable text,
  not scanned images; confirm chunks were actually indexed with
  `curl http://localhost:8080/api/rag/documents/stats`.
