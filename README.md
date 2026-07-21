# LLM Dev Kit

A local-first **microservices** LLM workspace. Chat through **Open WebUI**, answer with retrieval-augmented generation over your PDFs and GitHub docs, run **fully offline on Ollama**, and optionally route to **cloud LLMs (OpenAI, Anthropic, or any OpenAI-compatible API)** by adding an API key. All traffic enters through an **Nginx load balancer**.

See [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams and request flows, and
[docs/setup.md](docs/setup.md) for a full step-by-step setup and
troubleshooting guide.

## What You Get

- **Open WebUI** frontend (replaces the old Streamlit UI)
- **Nginx** gateway/load balancer — single entrypoint on `:8080`, round-robins across `rag-service` replicas
- **llm-service** — one API for all models: local Ollama by default, `openai/<model>` and `anthropic/<model>` when a key is configured (env or per-request)
- **rag-service** (2 replicas) — chat with hybrid retrieval (ChromaDB PDFs + Qdrant GitHub docs), PDF ingestion, Redis response cache, and an **OpenAI-compatible `/v1` API** so Open WebUI (or any OpenAI SDK) can use the RAG pipeline as a model backend
- **webhook-service** — GitHub push webhooks → Kafka events
- **embedding-worker** — Kafka consumer that chunks, embeds, and indexes GitHub markdown into Qdrant
- **mcp-service** — MCP tools backed by the same services
- Optimized Docker: one slim stage per service, per-service dependencies, non-root containers, healthchecks, hot reload in dev

## Services

| Service | Port (internal) | Purpose |
| --- | ---: | --- |
| `nginx` | `8080` (published) | Gateway + load balancer, the only published app port |
| `open-webui` | 8080 | Chat frontend |
| `llm-service` | 8010 | Model routing: Ollama (offline) + cloud providers |
| `rag-service` ×2 | 8020 | RAG chat, `/v1` OpenAI-compatible API, PDF ingest, cache |
| `webhook-service` | 8030 | GitHub webhook → Kafka |
| `embedding-worker` | — | Kafka consumer → Qdrant indexer |
| `mcp` | stdio | MCP tool server (profile `mcp`) |
| `redis` / `chroma` / `qdrant` / `kafka` | 6379 / 8000 / 6333 / 9092 | Infrastructure |

## Quick Start

1. **Start Ollama** (offline models):

   ```bash
   ollama serve
   ollama pull llama3.1
   ollama pull nomic-embed-text
   ```

   (Or run Ollama in Docker: `docker compose --profile ollama up` and set `OLLAMA_HOST=http://ollama:11434` in `.env` — CPU-only on macOS.)

2. **Configure** — copy `sample.env` to `.env`. Everything works offline with the defaults; cloud keys are optional.

3. **Run the stack**:

   ```bash
   docker compose up --build
   ```

4. Open **http://localhost:8080** — create the first (admin) account in Open WebUI.

In Open WebUI you'll see two kinds of models:

- **Ollama models** (direct connection) — plain offline chat.
- Models from the **`http://nginx/v1` connection** — the same models, but answered by `rag-service` with retrieval over your indexed documents.

> **Uploading PDFs:** the paperclip/attachment button inside an Open WebUI
> chat feeds Open WebUI's own built-in document store, not this project's
> retriever. To index a PDF here, upload it to the ingest endpoint instead
> (see [API Examples](#api-examples-through-the-load-balancer) below or the
> full walkthrough in [docs/setup.md](docs/setup.md#5-index-a-pdf)), then
> chat against a model from the `nginx/v1` connection.

## Cloud LLMs — bring your own API key

The stack is fully offline by default. To enable cloud models, either:

- **In `.env`** (server-wide): set `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`. Models then appear as `openai/gpt-4o`, `anthropic/claude-sonnet-5`, etc.
- **Per request**: pass `api_key` in the `/chat` or `/generate` request body — nothing stored server-side.
- **In Open WebUI**: Admin Settings → Connections → add any OpenAI-compatible API with your own key; a real (non `sk-local*`) key entered for the `/v1` RAG connection is forwarded to the cloud provider for `openai/...` / `anthropic/...` models.

`OPENAI_BASE_URL` may point at any OpenAI-compatible endpoint (Groq, Together, vLLM, LM Studio, ...). Embeddings always stay local so your vector stores keep one consistent embedding space.

## API Examples (through the load balancer)

```bash
# health
curl http://localhost:8080/api/llm/health
curl http://localhost:8080/api/rag/health

# all available models (local + configured cloud)
curl http://localhost:8080/api/llm/models

# RAG chat — offline model
curl -X POST http://localhost:8080/api/rag/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Summarize my knowledge base"}'

# RAG chat — cloud model with your own key
curl -X POST http://localhost:8080/api/rag/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello","model":"anthropic/claude-sonnet-5","api_key":"sk-ant-..."}'

# OpenAI-compatible API (works with any OpenAI SDK)
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.1","messages":[{"role":"user","content":"What changed in the docs?"}]}'

# ingest a PDF into the RAG index
curl -X POST http://localhost:8080/api/rag/ingest/pdf -F "file=@mydoc.pdf"
```

## GitHub Documentation Sync

`POST http://localhost:8080/webhooks/github` receives GitHub Push events (signature-verified when `GITHUB_WEBHOOK_SECRET` is set), publishes per-file events to Kafka `docs.changed`, and the embedding worker indexes changed `.md`/`.mdx` files into Qdrant. RAG chat automatically searches these documents alongside uploaded PDFs. Details in [docs/github-doc-sync.md](docs/github-doc-sync.md).

## MCP Usage

`mcp.json` is included for MCP clients. Tools: `list_models`, `ask_llm_dev_kit`.

```bash
docker compose --profile mcp run --rm mcp
```

## Scaling

`rag-service` runs 2 replicas by default (`deploy.replicas` in `docker-compose.yml`); Nginx round-robins across them. Scale at runtime:

```bash
docker compose up -d --scale rag-service=4
docker compose restart nginx   # re-resolve upstream IPs
```

## Local Development (outside Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt -r services/llm_service/requirements.txt \
  -r services/rag_service/requirements.txt
export PYTHONPATH=services
uvicorn llm_service.main:app --reload --port 8010
uvicorn rag_service.main:app --reload --port 8020
```

Use `sample.env` as the starting point for `.env` (set `LLM_SERVICE_URL=http://localhost:8010`).

## Testing

```bash
pip install -r requirements-dev.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

## Troubleshooting

- **Nothing loads at `localhost:8080`** — run `docker compose ps`; if services show `Exited`, the stack stopped (Docker Desktop restart, host sleep, or a manual `down`/`stop`) and needs `docker compose up -d`.
- **PDF uploaded via Open WebUI doesn't show up in RAG answers** — the chat attachment button doesn't feed this project's index; ingest it via the API instead (see [API Examples](#api-examples-through-the-load-balancer) above).
- **No models in Open WebUI** — check Ollama is running (`ollama list`) and reachable from Docker; the connection URL is `http://host.docker.internal:11434` by default.
- **Cloud model errors** — `401` means no/invalid API key: set it in `.env` or pass `api_key` per request.
- **PDF retrieval returns nothing** — the PDF must contain selectable text, not scanned images.
- **`docs.failed` events** — inspect worker logs: `docker compose logs -f embedding-worker`.

Full walkthrough and more failure modes: [docs/setup.md](docs/setup.md).
