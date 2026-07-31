# LLM Dev Kit

A local-first **microservices** LLM workspace. Chat through a **built-in lightweight web UI** (a single static page — no heavyweight frontend image), answer with retrieval-augmented generation over your PDFs and GitHub docs, run **fully offline on Ollama**, and optionally route to **cloud LLMs (OpenAI, Gemini, Anthropic) via LiteLLM** by adding an API key. All traffic enters through an **Nginx load balancer**.

See [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams and request flows, and
[docs/setup.md](docs/setup.md) for a full step-by-step setup and
troubleshooting guide.

## What You Get

- **Custom chat UI** — a React + Vite app compiled to ~50 kB of static files served by nginx (replaces the 1.5 GB Open WebUI image): streaming responses, PDF upload, provider/model picker, per-provider API keys, cache and index stats
- **Nginx** gateway/load balancer — single entrypoint on `:8080`, serves the UI and round-robins across `rag-service` replicas
- **llm-service** — one API for all models: local Ollama by default; `openai/<model>`, `gemini/<model>` and `anthropic/<model>` routed through **LiteLLM** with true token streaming (key from env or per-request)
- **rag-service** (2 replicas) — chat with hybrid retrieval (ChromaDB PDFs + Qdrant GitHub docs), streaming chat, PDF ingestion, Redis response cache, and an **OpenAI-compatible `/v1` API** (works with any OpenAI SDK — handy for LangChain later)
- **webhook-service** — GitHub push webhooks → Kafka events
- **embedding-worker** — Kafka consumer that chunks, embeds, and indexes GitHub markdown into Qdrant
- **mcp-service** — MCP tools backed by the same services
- Optimized Docker: one slim stage per service, per-service dependencies, non-root containers, healthchecks, hot reload in dev

## Services

| Service | Port (internal) | Purpose |
| --- | ---: | --- |
| `nginx` | `8080` (published) | Gateway + load balancer + static chat UI, the only published app port |
| `llm-service` | 8010 | Model routing: Ollama (offline) + cloud via LiteLLM |
| `rag-service` ×2 | 8020 | RAG chat (+streaming), `/v1` OpenAI-compatible API, PDF ingest, cache |
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

2. **Configure** — copy `sample.env` to `.env`, then set `AUTH_SECRET`:

   ```bash
   cp sample.env .env
   echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env
   ```

   `AUTH_SECRET` signs the web app's session cookies and has no default on
   purpose — the stack refuses to start without it. Everything else works
   offline with the defaults; cloud keys are optional.

3. **Run the stack**:

   ```bash
   docker compose up --build
   ```

4. Open **http://localhost:8080** — create an account, and you are in.

## Chat UI

The frontend is a **Next.js** application ([web/](web/)) running as its own
container, reverse-proxied by nginx at `/`. See [web/README.md](web/README.md)
for its architecture and environment variables.

- **Accounts** — email/password sign-in (optional GitHub OAuth), so history is per-user rather than per-browser.
- **Streaming responses** — tokens render as they arrive over SSE, with a stop button; a partial answer is persisted even if you stop it or the model host dies mid-sentence.
- **Multiple sessions and folders** — persistent history, colour-coded folders, pinning, and search across titles and message bodies.
- **Edit and regenerate** — editing a message rewinds the conversation to that turn and regenerates; replaced answers are archived and reachable through a `‹ 2/3 ›` control rather than lost.
- **Markdown and syntax highlighting** — GitHub-flavoured Markdown, per-block code copy and soft-wrap toggle.
- **Sharing** — publish any conversation as a read-only link, revocable at any time.
- **Dark & light mode** — follows your OS preference, toggleable, remembered.

> **Note:** the retrieval pipeline is unchanged — answers still come from
> `rag-service`, grounded in your indexed PDFs and GitHub docs. PDF ingestion
> is available through the `/api/rag/ingest/pdf` endpoint; the in-chat
> paperclip upload from the old static UI has not been reimplemented yet.
- **Cache badge** — repeated questions come back instantly from Redis and are marked ⚡ cached. Header shows live LLM/docs/cache status plus one-click cache clear.

Cloud models in the picker come from curated lists in [litellm_provider.py](services/llm_service/providers/litellm_provider.py) (`DEFAULT_CLOUD_MODELS`) — edit them there to add or pin models.

For UI development with hot reload (requires Node 20+):

```bash
cd ui
npm install
npm run dev   # http://localhost:5173, proxies /api and /v1 to :8080
```

## Cloud LLMs — bring your own API key

The stack is fully offline by default. Cloud calls go through **LiteLLM**, so adding more providers later is a one-line change. To enable cloud models, either:

- **In `.env`** (server-wide): set `OPENAI_API_KEY`, `GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY`. Models are addressed as `openai/gpt-4o`, `gemini/gemini-2.5-flash`, `anthropic/claude-sonnet-5`, etc.
- **Per request / in the UI**: pick a cloud provider and paste your key — it is sent as `api_key` in the request body and never stored server-side.

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

# RAG chat — streaming (NDJSON: meta, deltas, done)
curl -N -X POST http://localhost:8080/api/rag/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Summarize my knowledge base"}'

# RAG chat — cloud model with your own key
curl -X POST http://localhost:8080/api/rag/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello","model":"gemini/gemini-2.5-flash","api_key":"AIza..."}'

# OpenAI-compatible API (works with any OpenAI SDK)
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.1","messages":[{"role":"user","content":"What changed in the docs?"}]}'

# ingest a PDF into the RAG index
curl -X POST http://localhost:8080/api/rag/ingest/pdf -F "file=@mydoc.pdf"
```

### Using it from LangChain

The `/v1` endpoint is OpenAI-compatible, so LangChain can use the whole RAG pipeline as a chat model — no extra glue code:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:8080/v1",
    api_key="sk-local-rag",   # placeholder = stay offline; real key = cloud models
    model="llama3.1",         # or "gemini/gemini-2.5-flash", "openai/gpt-4o", ...
)
print(llm.invoke("Summarize my knowledge base").content)
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

## Project Layout

```
web/                       Next.js chat app — auth, history, folders, sharing
nginx/nginx.conf           gateway: web + /api/* + /v1 routing, LB across replicas
services/
  llm_service/             model router — Ollama direct, cloud via LiteLLM
  rag_service/             RAG chat (+streaming), /v1 API, PDF ingest, Redis cache
  webhook_service/         GitHub push webhooks → Kafka
  embedding_worker/        Kafka consumer → chunk/embed/index into Qdrant
  mcp_service/             MCP tool server
  devkit_common/           shared config, models, Kafka/Redis/Qdrant helpers
tests/                     unit tests (no containers needed)
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
- **"no local models found" in the model picker** — check Ollama is running (`ollama list`) and reachable from Docker; the connection URL is `http://host.docker.internal:11434` by default.
- **Cloud model errors** — `401` means no/invalid API key: set it in `.env` or pass `api_key` per request.
- **PDF retrieval returns nothing** — the PDF must contain selectable text, not scanned images.
- **`docs.failed` events** — inspect worker logs: `docker compose logs -f embedding-worker`.

Full walkthrough and more failure modes: [docs/setup.md](docs/setup.md).
