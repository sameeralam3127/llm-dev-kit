# LLM Dev Kit

A local-first **microservices** LLM workspace — and a **learning journey**.
Chat through a full-featured **Next.js app** (accounts, persistent history,
folders, sharing), answer with retrieval-augmented generation over your PDFs,
run **fully offline on Ollama**, and optionally route to **cloud LLMs
(OpenAI, Gemini, Anthropic) via LiteLLM** by adding an API key. All traffic
enters through an **Nginx load balancer**.

The project grows in phases — each one a hot-pluggable module behind an
interface, production-ready before the next begins — so you can fork it,
make small changes, and have your own live AI chatbot while learning how
each layer works. See **[docs/ROADMAP.md](docs/ROADMAP.md)** for the 11-phase
plan, [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams and request flows, and
[docs/setup.md](docs/setup.md) for step-by-step setup.


## What You Get

- **Full chat application** — a Next.js app ([web/](web/)) with accounts, streaming responses, persistent per-user history, chat folders, edit/regenerate with version history, Markdown + syntax highlighting, and revocable share links
- **Nginx** gateway/load balancer — single entrypoint on `:8080`, reverse-proxies the web app and round-robins across `rag-service` replicas
- **llm-service** — one API for all models: local Ollama by default; `openai/<model>`, `gemini/<model>` and `anthropic/<model>` routed through **LiteLLM** with true token streaming (key from env or per-request)
- **rag-service** (2 replicas) — chat with retrieval over ChromaDB (uploaded PDFs), streaming chat, PDF ingestion, Redis response cache, and an **OpenAI-compatible `/v1` API** (works with any OpenAI SDK — handy for LangChain later)
- **mcp-service** — MCP tools backed by the same services
- Optimized Docker: one slim stage per service, per-service dependencies, non-root containers, healthchecks, hot reload in dev

## Services

| Service | Port (internal) | Purpose |
| --- | ---: | --- |
| `nginx` | `8080` (published) | Gateway + load balancer, the only published port |
| `web` | 3000 | Next.js chat app — accounts, history, folders, sharing |
| `llm-service` | 8010 | Model routing: Ollama (offline) + cloud via LiteLLM |
| `rag-service` ×2 | 8020 | RAG chat (+streaming), `/v1` OpenAI-compatible API, PDF ingest, cache |
| `mcp` | stdio | MCP tool server (profile `mcp`) |
| `redis` / `chroma` | 6379 / 8000 | Infrastructure |

## Quick Start

1. **Start Ollama** (offline models):

   ```bash
   ollama serve
   ollama pull llama3.1
   ollama pull nomic-embed-text
   ```

   (Or run Ollama in Docker: `docker compose --profile ollama up` and set `OLLAMA_HOST=http://ollama:11434` in `.env` — CPU-only on macOS.)

2. **Configure** — copy `.env.example` to `.env`, then set `AUTH_SECRET`:

   ```bash
   cp .env.example .env
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

## Where the project is

The build is phase-wise on purpose: each phase lands as a hot-pluggable module
behind an interface and is production-ready before the next begins, so you can
fork this, learn one concept at a time, and still have a working chatbot the
whole way through.

| | Phase | Seam it plugs into |
| --- | --- | --- |
| ✅ | **1 — Foundation** — the full chat app you get today | `ChatProvider` (`web/src/lib/llm/types.ts`) |
| 🚧 | **2 — Multi-Model AI** — adapters for OpenAI, Anthropic, Gemini, Groq, LM Studio… | `ChatProvider` + a provider registry |
| | 3 — Memory · 4 — RAG 2.0 · 5 — Agents · 6 — Coding assistant | see the roadmap |
| | 7 — Workspace · 8 — Voice · 9 — Multimodal · 10 — Enterprise · 11 — Orchestration | see the roadmap |

**Starting Phase 2** means writing one adapter against an interface that
already exists — no rewiring of routes or UI. That is the whole point of the
seam. Full detail, including each phase's seam, is in
**[docs/ROADMAP.md](docs/ROADMAP.md)**.

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

Answers still come from `rag-service`, grounded in your indexed PDFs — the
retrieval pipeline is unchanged. The model picker is fed by
`rag-service`'s `/v1/models`, which lists local Ollama models plus whichever
cloud models are configured (see [Cloud LLMs](#cloud-llms--bring-your-own-api-key)).

**Not carried over from the old static UI** (tracked in
[docs/ROADMAP.md](docs/ROADMAP.md)): in-chat PDF upload — ingestion still works
via `POST /api/rag/ingest/pdf`; the ⚡ cache badge and one-click cache clear;
and pasting a cloud API key from the browser, which is now a server-side
setting instead.

For frontend development with hot reload (requires Node 20+):

```bash
cd web
npm install
cp .env.example .env          # set AUTH_SECRET, point LLM_BASE_URL at the stack
npm run db:push && npm run db:seed
npm run dev                   # http://localhost:3000
```

## Cloud LLMs — bring your own API key

The stack is fully offline by default. Cloud calls go through **LiteLLM**, so adding more providers later is a one-line change. To enable cloud models, either:

- **In `.env`** (server-wide): set `OPENAI_API_KEY`, `GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY`. Models are addressed as `openai/gpt-4o`, `gemini/gemini-2.5-flash`, `anthropic/claude-sonnet-5`, etc. These then appear in the web app's model picker.
- **Per request** (direct API calls): pass `api_key` in the request body to `/api/rag/chat`, or as a `Bearer` token to `/v1/chat/completions` — never stored server-side. Note this is an API-level feature; the web app itself has no per-user key field, so it uses the server-wide keys above.

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
  -d '{"model":"llama3.1","messages":[{"role":"user","content":"Summarize my knowledge base"}]}'

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
  src/lib/llm/             ChatProvider seam — add a model host here (Phase 2)
  src/server/services/     all DB mutation + ownership checks live here
  src/app/api/             routes: parse → delegate → serialise, nothing more
  README.md                web-specific architecture and env vars
nginx/nginx.conf           gateway: web + /api/* + /v1 routing, LB across replicas
services/                 each service is an installable package: src/<name>/ + pyproject.toml + requirements.txt
  llm_service/             model router — Ollama direct, cloud via LiteLLM
  rag_service/             RAG chat (+streaming), /v1 API, PDF ingest, Redis cache
  mcp_service/             MCP tool server
  devkit_common/           shared config, models
docs/ROADMAP.md            the 11 phases and the seam each one plugs into
docs/setup.md              step-by-step setup and troubleshooting
tests/                     unit tests (no containers needed)
```

The three boundaries worth knowing before you change anything: token generation
goes through `ChatProvider`, database writes and ownership checks live only in
`web/src/server/services/`, and route handlers parse, delegate and serialise —
they never query the database directly. Keeping to those is what makes each
roadmap phase a drop-in rather than a rewrite.

## Local Development (outside Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e services/devkit_common -e services/llm_service -e services/rag_service
uvicorn llm_service.main:app --reload --port 8010
uvicorn rag_service.main:app --reload --port 8020
```

Use `.env.example` as the starting point for `.env` (set `LLM_SERVICE_URL=http://localhost:8010`).

## Testing

```bash
# python services
pip install -r requirements-dev.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest

# web app — the gate before any change lands
cd web && npm run typecheck && npm run lint && npm run build
```

## Troubleshooting

- **`docker compose up` fails immediately with "required variable AUTH_SECRET is missing"** — expected: the web app's session key has no default. Run `echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env`.
- **Nothing loads at `localhost:8080`** — run `docker compose ps`; if services show `Exited`, the stack stopped (Docker Desktop restart, host sleep, or a manual `down`/`stop`) and needs `docker compose up -d`.
- **Signed in, but every message errors** — the web app reaches `rag-service` directly at `http://rag-service:8020/v1`. Check `docker compose logs -f web rag-service`; a `503` here means the RAG service is not healthy yet.
- **"no local models found" in the model picker** — check Ollama is running (`ollama list`) and reachable from Docker; the connection URL is `http://host.docker.internal:11434` by default.
- **Cloud model errors** — `401` means no/invalid API key: set it in `.env` or pass `api_key` per request.
- **PDF retrieval returns nothing** — the PDF must contain selectable text, not scanned images.

Full walkthrough and more failure modes: [docs/setup.md](docs/setup.md).
