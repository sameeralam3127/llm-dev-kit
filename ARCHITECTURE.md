# Architecture

The LLM Dev Kit is a set of small, independently built and deployed services
behind an Nginx gateway. The only published application port is the gateway
(`:8080`). Every service has its own Docker image stage, its own dependency
set, and communicates over HTTP or Kafka — no shared in-process imports across
service boundaries (only the thin `devkit_common` library is shared at build
time).

## System Overview

```mermaid
flowchart TB
    subgraph Client
        B[Browser]
        GH[GitHub Push]
        SDK[Any OpenAI SDK / curl]
        MCPC[MCP Client]
    end

    subgraph Gateway
        N[Nginx :8080<br/>reverse proxy + load balancer<br/>+ static chat UI]
    end

    subgraph Services
        R1[rag-service replica 1 :8020]
        R2[rag-service replica 2 :8020]
        L[llm-service :8010]
        W[webhook-service :8030]
        EW[embedding-worker]
        MCP[mcp-service stdio]
    end

    subgraph Infrastructure
        RD[(Redis<br/>response cache)]
        CH[(ChromaDB<br/>PDF vectors)]
        QD[(Qdrant<br/>GitHub doc vectors)]
        K[[Kafka<br/>docs.changed / indexed / failed]]
    end

    subgraph Models
        OL[Ollama<br/>fully offline]
        LL[LiteLLM<br/>OpenAI / Gemini / Anthropic]
    end

    B -->|/ static chat UI| N
    SDK --> N
    GH -->|/webhooks/github| N
    N -->|/v1 and /api/rag round-robin| R1
    N --> R2
    N -->|/api/llm| L
    N --> W
    R1 --> RD
    R1 --> CH
    R1 --> QD
    R1 --> L
    R2 --> L
    W --> K
    K --> EW
    EW --> L
    EW --> QD
    EW --> RD
    MCPC --> MCP
    MCP --> R1
    MCP --> L
    L -->|default| OL
    L -->|provider/model + API key| LL
```

## Services

### nginx (gateway / load balancer / frontend)
Single entrypoint. Serves the static chat UI (`./ui`, bind-mounted — no
frontend container or image to pull), routes APIs by path, and round-robins
across all `rag-service` replicas (Docker DNS returns one address per
replica; nginx resolves them at startup). SSE/NDJSON buffering is disabled so
token streaming reaches the browser.

| Route | Target |
| --- | --- |
| `/` | static chat UI (`ui/index.html`) |
| `/v1/*` | rag-service — OpenAI-compatible API |
| `/api/rag/*` | rag-service REST (prefix stripped) |
| `/api/llm/*` | llm-service REST (prefix stripped) |
| `/webhooks/*` | webhook-service |

### chat UI (static)
A single dependency-free HTML page: streaming chat over
`/api/rag/chat/stream`, PDF upload to `/api/rag/ingest/pdf`, provider/model
picker fed by `/api/llm/models`, per-provider API keys kept in browser
localStorage and sent per-request, cache/index status badges, and source
snippets under each answer.

### llm-service (model router)
The only service that talks to model backends. Providers:

- **ollama** (default, offline) — chat, streaming, embeddings, direct API.
- **openai / gemini / anthropic** — routed through **LiteLLM**
  (`litellm.acompletion`), with true token streaming for cloud models.
  `OPENAI_BASE_URL` still lets the `openai/` prefix target any
  OpenAI-compatible API.

Model ids route by prefix: `llama3.1` → Ollama, `openai/gpt-4o` → OpenAI,
`gemini/gemini-2.5-flash` → Gemini, `anthropic/claude-sonnet-5` → Anthropic.
Cloud calls need a key from the environment **or** an `api_key` field on the
request (bring-your-own-key — nothing is stored). Embeddings are always local
so both vector stores share one embedding space. Errors are proper HTTP
errors — they are never returned as fake chat text and never cached.

Endpoints: `/health`, `/providers`, `/models`, `/generate`,
`/generate/stream` (NDJSON), `/embed`.

### rag-service (×2 replicas)
Chat orchestration: Redis cache check → embed query (via llm-service) →
retrieve context from **ChromaDB** (uploaded PDFs) and **Qdrant** (GitHub
docs, score-thresholded) → build prompt → generate via llm-service → cache
successful responses (keys namespaced `chat:*`, so clearing chat cache never
touches worker state).

Also serves `/chat/stream` (NDJSON token streaming for the chat UI), the
OpenAI-compatible `/v1/models` and `/v1/chat/completions` (streaming SSE and
non-streaming), `/ingest/pdf`, `/cache/*`, `/documents/*`.

### webhook-service
Verifies the GitHub `X-Hub-Signature-256` (HMAC) when a secret is configured,
extracts changed `.md`/`.mdx` files from push payloads, and publishes one
`docs.changed` event per file to Kafka **keyed by file path** so per-file
ordering is preserved across partitions. The Kafka producer is created once
at startup and closed on shutdown.

### embedding-worker
Kafka consumer (`embedding-workers` group, manual commits). Per event:
dedup-check in Redis → download markdown from GitHub (Redis-cached per
commit) → chunk → embed via llm-service → **delete the file's previous
vectors** → upsert into Qdrant → publish `docs.indexed`. Failures publish
`docs.failed` and the worker moves on — a poison message can never crash-loop
the consumer. Removed files delete their vectors.

### mcp-service
MCP tools (`list_models`, `ask_llm_dev_kit`) that call llm-service and
rag-service over HTTP — no direct database access.

## Chat Request Flow (RAG, streaming)

```mermaid
sequenceDiagram
    participant U as Chat UI (browser)
    participant N as Nginx
    participant R as rag-service (replica)
    participant L as llm-service
    participant V as Chroma + Qdrant
    participant M as Ollama / LiteLLM cloud

    U->>N: POST /api/rag/chat/stream
    N->>R: round-robin to a replica
    R->>R: Redis cache check (hit → stream cached answer)
    R->>L: POST /embed (query)
    L->>M: local embedding model
    R->>V: vector search (PDFs + GitHub docs)
    R->>L: POST /generate/stream (prompt + context)
    L->>M: Ollama or LiteLLM token stream
    L-->>R: NDJSON deltas
    R-->>U: NDJSON (meta + deltas + done), full answer cached
```

## GitHub Doc Sync Flow

```mermaid
sequenceDiagram
    participant GH as GitHub
    participant N as Nginx
    participant W as webhook-service
    participant K as Kafka
    participant E as embedding-worker
    participant L as llm-service
    participant Q as Qdrant

    GH->>N: POST /webhooks/github (push)
    N->>W: verify HMAC signature
    W->>K: docs.changed (key = file path)
    K->>E: consume (manual commit)
    E->>GH: download raw markdown
    E->>L: POST /embed (chunks)
    E->>Q: delete old vectors, upsert new
    E->>K: docs.indexed | docs.failed
```

## Docker Build Strategy

One `Dockerfile`, one stage per service off a shared patched `python:3.12-slim`
base:

- each stage installs **only that service's** `requirements.txt` (rag-service
  uses the thin `chromadb-client` instead of the full chromadb package);
- containers run as a non-root `appuser`;
- healthchecks use the Python stdlib (no curl in the images);
- in dev, `docker-compose.yml` bind-mounts the service source and runs
  uvicorn `--reload` for hot reload;
- `deploy.replicas: 2` on rag-service demonstrates horizontal scaling behind
  the load balancer (`docker compose up -d --scale rag-service=N`).

## Offline / Cloud Model Matrix

| Scenario | Configuration | What happens |
| --- | --- | --- |
| Fully offline (default) | no keys set | All chat + embeddings via local Ollama |
| Server-wide cloud | `OPENAI_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` in `.env` | `openai/*`, `gemini/*`, `anthropic/*` models usable by everyone |
| Bring-your-own-key | key pasted in the UI (sent as `api_key`), or a real Bearer key on `/v1` | Key used for that request only, never stored |
| Alternative OpenAI-compatible host | `OPENAI_BASE_URL` | Groq/Together/vLLM/LM Studio behind the same `openai/` prefix |
