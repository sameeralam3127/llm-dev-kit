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
- Optional: a GitHub token + webhook secret, if you want GitHub doc sync
  (see [github-doc-sync.md](github-doc-sync.md))

## 1. Pull the local models

```bash
ollama serve
ollama pull llama3.1
ollama pull nomic-embed-text
```

`nomic-embed-text` is required even if you only ever use cloud chat models —
embeddings always run locally so both vector stores share one consistent
embedding space.

## 2. Configure environment

```bash
cp sample.env .env
```

Everything works fully offline with the defaults. The sections in `.env` map
to:

| Section | Purpose |
| --- | --- |
| Offline LLM | `OLLAMA_HOST`, default chat/embedding models |
| Cloud providers | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` — leave blank to stay offline |
| Service URLs | Only used when running a service outside Docker |
| Cache | Redis URL + response cache TTL |
| Vector stores | Chroma (PDFs) + Qdrant (GitHub docs) connection info |
| Kafka | Broker address + topic names for doc sync |
| GitHub sync | Token, webhook secret, default owner/repo/branch |

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

## 4. Open Open WebUI

Go to **http://localhost:8080** and create the first (admin) account. You'll
see two kinds of models in the picker:

- **Ollama models** — direct connection, plain offline chat, no retrieval.
- **Models from the `http://nginx/v1` connection** — same models, but
  answered by `rag-service` with retrieval over whatever you've indexed.

Use the second group to get RAG-augmented answers.

## 5. Index a PDF

**Important:** the paperclip/attachment button inside an Open WebUI chat
uses Open WebUI's *own* built-in document store — it does not feed this
project's retriever. To get a PDF into this project's index, upload it
directly to the ingest endpoint:

```bash
curl -X POST http://localhost:8080/api/rag/ingest/pdf -F "file=@mydoc.pdf"
# {"chunks": 12}
```

Then chat against a model from the `nginx/v1` connection (step 4) and it
will automatically retrieve relevant chunks. Useful checks:

```bash
# how many chunks are currently indexed
curl http://localhost:8080/api/rag/documents/stats

# wipe the PDF index
curl -X POST http://localhost:8080/api/rag/documents/clear
```

The PDF must contain selectable text — scanned image pages produce zero
chunks and a 400 response.

## 6. GitHub documentation sync (optional)

Point a GitHub webhook at `http://<host>:8080/webhooks/github` and set
`GITHUB_WEBHOOK_SECRET`; pushed `.md`/`.mdx` changes are chunked and indexed
into Qdrant automatically, and RAG chat searches them alongside uploaded
PDFs. Full details in [github-doc-sync.md](github-doc-sync.md).

## 7. Cloud models (optional)

Set `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` in `.env` (server-wide), pass
`api_key` per request to `/api/rag/chat`, or add a connection with your own
key in Open WebUI's Admin Settings → Connections. See the README's
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
pip install -r requirements-dev.txt -r services/llm_service/requirements.txt \
  -r services/rag_service/requirements.txt
export PYTHONPATH=services
uvicorn llm_service.main:app --reload --port 8010
uvicorn rag_service.main:app --reload --port 8020
```

Use `sample.env` as a starting point and set `LLM_SERVICE_URL=http://localhost:8010`.

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
- **PDF doesn't show up in chat answers after uploading it in Open WebUI** —
  the chat attachment button doesn't call this project's ingest pipeline;
  use `curl .../api/rag/ingest/pdf` as shown in [step 5](#5-index-a-pdf).
- **No models in Open WebUI** — check Ollama is running (`ollama list`) and
  reachable from Docker; the connection URL is
  `http://host.docker.internal:11434` by default.
- **Cloud model errors** — `401` means no/invalid API key: set it in `.env`
  or pass `api_key` per request.
- **PDF retrieval returns nothing** — the PDF must contain selectable text,
  not scanned images; confirm chunks were actually indexed with
  `curl http://localhost:8080/api/rag/documents/stats`.
- **`docs.failed` events** — inspect worker logs:
  `docker compose logs -f embedding-worker`.
