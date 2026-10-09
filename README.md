# LLM Dev Kit

**A local-first, production-structured LLM workspace that runs entirely on your own machine.**

Chat through a full-featured Next.js app with accounts, persistent history, folders and sharing. Answer with retrieval-augmented generation over your own PDFs. Run entirely offline on Ollama, or route to cloud models (OpenAI, Gemini, Anthropic) with a single API key. Every service is independently built, deployed and scaled behind an Nginx gateway — the same shape a small production system actually takes, not a toy demo.

![Next.js 15](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)
![React 19](https://img.shields.io/badge/React-19-149eca?logo=react&logoColor=white)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![GitHub stars](https://img.shields.io/github/stars/sameeralam3127/llm-dev-kit?style=flat&logo=github)

Every swappable piece — model providers, embeddings, the vector store, document loaders, chunkers and MCP tools — is a plugin behind a typed interface, so you can replace one without touching the services that use it.

---

## Table of Contents

- [Highlights](#highlights)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Where the Project Is](#where-the-project-is)
- [Services](#services)
- [Chat UI](#chat-ui)
- [Configuration & Cloud LLMs](#configuration--cloud-llms)
- [API Reference](#api-reference)
- [MCP Usage](#mcp-usage)
- [Scaling](#scaling)
- [Plugins](#plugins)
- [Project Layout](#project-layout)
- [Local Development](#local-development-outside-docker)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Learn More](#learn-more)

---

## Highlights

- **Full chat application** — a Next.js app ([web/](web/)) with accounts, streaming responses, persistent per-user history, chat folders, edit/regenerate with version history, Markdown + syntax highlighting, and revocable share links.
- **Nginx gateway** — the single published entrypoint (`:8080`); reverse-proxies the web app and round-robins across `rag-service` replicas. Comes up within seconds of `docker compose up` and serves a branded fallback page while the backend finishes warming up, instead of a blank tab or a raw connection error.
- **llm-service** — one API for every model: local Ollama by default, or `openai/<model>`, `gemini/<model>` and `anthropic/<model>` routed through **LiteLLM** with true token streaming. Each provider is a plugin; installing another one makes its `prefix/` routable.
- **rag-service** (2 replicas) — chat with retrieval over ChromaDB (your uploaded PDFs), streaming chat, PDF ingestion, a Redis response cache, and an **OpenAI-compatible `/v1` API** that works with any OpenAI SDK — including LangChain.
- **mcp-service** — every installed tool plugin exposed over MCP, for use from any MCP-compatible client.
- **Plugin core** — `ldk_core` defines the interfaces (LLM provider, embedder, vector store, loader, chunker, tool, auth, rate limiter, storage), discovers plugins through Python entry points, and ships a contract test suite per interface that every implementation must pass.
- **Operable services** — one JSON error shape across the Python services and the web app, structured JSON logs with a request id on every line, and configuration that fails at startup with every bad variable named.
- **Production-minded Docker setup** — pinned image versions (no floating `:latest` tags), BuildKit cache-mount builds (a `requirements.txt` change reinstalls in seconds, not minutes), per-service CPU/memory limits and reservations, non-root containers, and stdlib healthchecks. See [ARCHITECTURE.md](ARCHITECTURE.md) for the full build strategy.

## Requirements

| For | You need |
| --- | --- |
| Running the full stack | Docker with Compose v2 (`docker compose`, not the standalone `docker-compose`) |
| Chat + embeddings, fully offline | [Ollama](https://ollama.com) installed on the host — or run it in the `ollama` Compose profile instead |
| Cloud models (optional) | An API key for OpenAI, Gemini and/or Anthropic |
| Frontend development outside Docker | Node.js 20+ |
| Python service development outside Docker | Python 3.12+ |

## Quick Start

1. **Start Ollama** (offline models):

   ```bash
   ollama serve
   ollama pull llama3.1
   ollama pull nomic-embed-text
   ```

   Or run Ollama in Docker instead: `docker compose --profile ollama up` and set `OLLAMA_HOST=http://ollama:11434` in `.env` (CPU-only on macOS).

2. **Configure** — copy `.env.example` to `.env`, then set `AUTH_SECRET`:

   ```bash
   cp .env.example .env
   echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env
   ```

   `AUTH_SECRET` signs the web app's session cookies and has no default on purpose — the stack refuses to start without it. Everything else works offline with the defaults; cloud keys are optional.

3. **Run the stack**:

   ```bash
   docker compose up --build
   ```

4. Open **http://localhost:8080** — create an account, and you're in.

## Where the Project Is

The next major version turns the kit into a sovereign, local-first private AI workspace: every swappable capability behind an interface with a plugin registry, offline by default, and documents, identity and rate limits per user. It is **in development, not released** — `main` carries the finished phases, and nothing is tagged as v2 yet. The plan of record is **[docs/v2/PLAN.md](docs/v2/PLAN.md)**; progress is tracked in [issue #20](https://github.com/sameeralam3127/llm-dev-kit/issues/20).

| | Phase | |
| --- | --- | --- |
| ✅ | **1 — Plan** | [docs/v2/PLAN.md](docs/v2/PLAN.md) |
| ✅ | **2 — Core refactor** | `ldk_core` interfaces + plugin registry; providers, stores, loaders, chunkers and MCP tools are plugins; CI gates every image |
| | 3 — Sovereign mode · 4 — Auth · 5 — Per-user ingestion on pgvector | |
| | 6 — Limits, observability, audit · 7 — Admin · 8 — Plugin marketplace · 9 — Distribution | |

Until Phase 4, the Python APIs (including `/v1`) are unauthenticated: keep the stack on a trusted network.

## Services

| Service | Port (internal) | Purpose |
| --- | ---: | --- |
| `nginx` | `8080` (published) | Gateway + load balancer, the only published port |
| `web` | 3000 | Next.js chat app — accounts, history, folders, sharing |
| `llm-service` | 8010 | Model routing over the LLM and embedder plugins: Ollama (offline) + cloud via LiteLLM |
| `rag-service` ×2 | 8020 | RAG chat (+streaming), `/v1` OpenAI-compatible API, PDF ingest, cache |
| `mcp` | stdio | MCP server for every tool plugin (profile `mcp`) |
| `redis` / `chroma` | 6379 / 8000 | Infrastructure |

Every service builds off its own Dockerfile stage with only the dependencies it needs, runs as a non-root user, and carries a CPU/memory limit sized to its actual workload — see [ARCHITECTURE.md](ARCHITECTURE.md#docker-build-strategy) for the full breakdown.

Each one is also published as its own image to GitHub Container Registry on every push to `main` ([.github/workflows/publish.yml](.github/workflows/publish.yml)), tagged `latest` and by commit SHA — but only after CI (lint, typecheck, tests, and a build-and-start check of every image) passes:

```bash
docker pull ghcr.io/sameeralam3127/llm-dev-kit-gateway:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-web:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-llm-service:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-rag-service:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-mcp-service:latest
```

`docker-compose.yml` still builds locally by default — pulling from GHCR is for running the stack without a local build (or in another environment) rather than a replacement for `docker compose up`.

## Chat UI

The frontend is a **Next.js** application ([web/](web/)) running as its own container, reverse-proxied by nginx at `/`. See [web/README.md](web/README.md) for its architecture and environment variables.

- **Accounts** — email/password sign-in (optional GitHub OAuth), so history is per-user rather than per-browser.
- **Streaming responses** — tokens render as they arrive over SSE, with a stop button; a partial answer is persisted even if you stop it or the model host dies mid-sentence. Only the growing part of the answer re-renders each frame, so long answers stay smooth.
- **Multiple sessions and folders** — persistent history, colour-coded folders, pinning, and search across titles and message bodies.
- **Edit and regenerate** — editing a message rewinds the conversation to that turn and regenerates; replaced answers are archived and reachable through a `‹ 2/3 ›` control rather than lost.
- **Markdown and syntax highlighting** — GitHub-flavoured Markdown, per-block code copy and soft-wrap toggle. The highlighter loads only when an answer contains code, and a code block is coloured once it closes.
- **Sharing** — publish any conversation as a read-only link, revocable at any time.
- **Dark & light mode** — follows your OS preference, toggleable, remembered.

Answers come from `rag-service`, grounded in your indexed PDFs — the retrieval pipeline is unchanged. The model picker is fed by `rag-service`'s `/v1/models`, which lists local Ollama models plus whichever cloud models are configured (see [Configuration & Cloud LLMs](#configuration--cloud-llms)).

> **Note:** three things from the project's earlier static UI didn't carry over as-is: in-chat PDF upload (ingestion still works via `POST /api/rag/ingest/pdf`), the cache badge and one-click cache clear, and pasting a cloud API key from the browser — that's now a server-side setting instead. Upload in the UI returns with per-user ingestion ([#15](https://github.com/sameeralam3127/llm-dev-kit/issues/15)).

For frontend development with hot reload:

```bash
cd web
npm install
cp .env.example .env          # set AUTH_SECRET, point LLM_BASE_URL at the stack
npm run db:push && npm run db:seed
npm run dev                   # http://localhost:3000
```

## Configuration & Cloud LLMs

The stack is fully offline by default. Cloud calls go through the **LiteLLM** plugin; a provider LiteLLM doesn't cover can be added as its own plugin (see [Plugins](#plugins)). To enable cloud models, either:

- **In `.env`** (server-wide): set `OPENAI_API_KEY`, `GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY`. Models are addressed as `openai/gpt-4o`, `gemini/gemini-2.5-flash`, `anthropic/claude-sonnet-5`, etc. These then appear in the web app's model picker.
- **Per request** (direct API calls): pass `api_key` in the request body to `/api/rag/chat`, or as a `Bearer` token to `/v1/chat/completions` — never stored server-side. This is an API-level feature; the web app itself has no per-user key field, so it uses the server-wide keys above.

`OPENAI_BASE_URL` may point at any OpenAI-compatible endpoint (Groq, Together, vLLM, LM Studio, ...). Embeddings always stay local so your vector store keeps one consistent embedding space; the embedding model is fixed per deployment (`DEFAULT_EMBEDDING_MODEL`, plus `EMBEDDING_DIMENSION` for models llm-service doesn't already know).

Logging is set with `LOG_LEVEL` and `LOG_FORMAT` (`json`, the default, or `console` for local reading).

## API Reference

All examples go through the load balancer at `:8080`.

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
  -d '{"model":"llama3.1","messages":[{"role":"user","content":"Summarize my knowledge base"}]}'

# ingest a PDF into the RAG index
curl -X POST http://localhost:8080/api/rag/ingest/pdf -F "file=@mydoc.pdf"
```

### Errors and request ids

Every error from the Python services and the web app has the same shape, with the HTTP status following from `code`:

```json
{"error": {"code": "invalid_request", "message": "Request validation failed",
           "details": [{"path": "body.texts",
                        "message": "List should have at least 1 item after validation, not 0"}]}}
```

Codes: `invalid_request` (400), `unauthorized` (401), `forbidden` (403), `not_found` (404), `conflict` (409), `rate_limited` (429), `internal` (500), `upstream_error` (502), `upstream_unavailable` (503), `timeout` (504). Every response from the Python services (`/v1`, `/api/rag`, `/api/llm`) carries an `X-Request-ID` header — send your own to correlate a call with their logs, where each line records it as `correlation_id`.

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

## Plugins

A plugin is a small Python distribution: an implementation of one interface from `ldk_core.ports`, a manifest (`llm-dev-kit-plugin.json`: name, version, kind, declared permissions and a JSON Schema for its configuration), and an entry point the services discover at startup:

```toml
[project.entry-points."llm_dev_kit.plugins"]
"llm.my-host" = "my_plugin:plugin"     # <kind>.<name>, matching the manifest
```

Its tests subclass the contract suite for that interface — the same suite the first-party plugins in [services/plugins/](services/plugins/) pass. `ldk-core` is not published to PyPI; install it from this checkout with `pip install -e "services/core[testing]"`.

```python
import pytest
from ldk_core.testing.contracts import LLMProviderContract

class TestMyHost(LLMProviderContract):
    @pytest.fixture
    def provider(self): return MyHostProvider(...)

    @pytest.fixture
    def model(self): return "my-model"
```

Plugins run in-process with the service's permissions; the manifest's `permissions` are disclosure, not a sandbox. Signed installs and an admin approval flow are planned for Phase 8.

## Project Layout

```
web/                       Next.js chat app — auth, history, folders, sharing
  src/lib/llm/             ChatProvider seam — the web app's own model adapter
  src/server/services/     all DB mutation + ownership checks live here
  src/app/api/             routes: parse → delegate → serialise, nothing more
  src/components/markdown/ block-by-block Markdown, on-demand syntax highlighting
  README.md                web-specific architecture and env vars
nginx/nginx.conf           gateway: web + /api/* + /v1 routing, LB across replicas
services/                  each service is an installable package: src/<name>/ + pyproject.toml + requirements.txt
  core/                     ldk_core: the ports, plugin registry, errors, settings, logging
  plugins/                  first-party plugins (ollama, litellm, chroma, loader_pdf, chunker_fixed, tools)
  llm_service/              model router over the LLM and embedder plugins
  rag_service/              RAG chat (+streaming), /v1 API, PDF ingest, Redis cache
  mcp_service/              MCP server exposing every Tool plugin
  devkit_common/            shared config, models, FastAPI service setup
docs/v2/PLAN.md            the v2 plan: architecture, interfaces, phases
docs/setup.md              step-by-step setup and troubleshooting
tests/                     Python unit, contract and service tests (no containers needed)
.github/workflows/         ci.yml (every push and PR) and publish.yml (main, after CI)
```

The three boundaries worth knowing before you change anything: token generation goes through `ChatProvider`, database writes and ownership checks live only in `web/src/server/services/`, and route handlers parse, delegate and serialise — they never query the database directly. On the Python side the same rule holds: services get implementations from the plugin registry and never import a plugin directly (`tests/test_architecture.py` enforces it).

## Local Development (outside Docker)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # also installs ldk_core and every plugin, editable
pip install -e services/devkit_common -e services/llm_service -e services/rag_service
uvicorn llm_service.main:app --reload --port 8010
uvicorn rag_service.main:app --reload --port 8020
```

Use `.env.example` as the starting point for `.env` (set `LLM_SERVICE_URL=http://localhost:8010`, and `LOG_FORMAT=console` for readable logs). Plugins are found through their installed entry points, so a new plugin needs `pip install -e` before a service sees it.

## Testing

```bash
# python services — the same checks CI runs (.github/workflows/ci.yml)
pip install -r requirements-dev.txt
ruff check services tests && ruff format --check services tests
mypy
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest

# the Chroma plugin's contract suite needs a real Chroma (CI runs one);
# without this it is skipped
docker run -d -p 8000:8000 chromadb/chroma:1.5.9
LDK_TEST_CHROMA_HOST=localhost python3 -m pytest tests/plugins/test_chroma_plugin.py

# web app — the gate before any change lands
cd web && npm run typecheck && npm run lint && npm test && npm run build
npm run bench    # streaming render cost, before/after (not part of CI)
```

CI runs all of this on every push and pull request, plus a job that builds each Python image, starts it and waits for `/health`.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `docker compose up` fails immediately with `"required variable AUTH_SECRET is missing"` | Expected — the web app's session key has no default. Run `echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env`. |
| Nothing loads at `localhost:8080` | Run `docker compose ps`; if services show `Exited`, the stack stopped (Docker Desktop restart, host sleep, or a manual `down`/`stop`) and needs `docker compose up -d`. |
| Signed in, but every message errors | The web app reaches `rag-service` directly at `http://rag-service:8020/v1`. Check `docker compose logs -f web rag-service`; a `503` here means the RAG service is not healthy yet. |
| "no local models found" in the model picker | Check Ollama is running (`ollama list`) and reachable from Docker; the connection URL is `http://host.docker.internal:11434` by default. |
| Cloud model errors | `401` means no/invalid API key: set it in `.env` or pass `api_key` per request. |
| PDF retrieval returns nothing | The PDF must contain selectable text, not scanned images. |
| A Python service exits at startup with `Invalid environment configuration:` | The message lists every bad variable; fix those in `.env` (or the compose environment). |
| llm-service exits with `Unknown embedding dimension for Ollama model …` | `DEFAULT_EMBEDDING_MODEL` is a model llm-service doesn't know; set `EMBEDDING_DIMENSION` to its vector length. |
| Logs at startup show `plugin skipped` | An installed plugin failed to load; the line names the entry point and the reason. The service keeps running without it. |

Full walkthrough and more failure modes: [docs/setup.md](docs/setup.md).

## Learn More

| Document | Covers |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System diagrams, request flows, and the Docker build strategy |
| [docs/v2/PLAN.md](docs/v2/PLAN.md) | The v2 plan: target architecture, interfaces, migration and phases |
| [docs/setup.md](docs/setup.md) | Step-by-step setup, PDF ingestion, and troubleshooting |
| [web/README.md](web/README.md) | Frontend architecture, environment variables, and feature detail |
