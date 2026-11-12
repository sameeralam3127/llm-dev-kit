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

The sections in `.env` map to the table below. `.env.example` sets
`OLLAMA_HOST=http://host.docker.internal:11434`, which is right for the Docker
stack, where Ollama runs on your machine. Only services run directly on your
machine need `http://localhost:11434` instead.

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

This runs the services from the code baked into their images. For hot reload
while working on the Python services, add the dev overlay, which bind-mounts
their source and runs uvicorn with `--reload`:

```bash
docker compose -f docker-compose.yml -f compose.dev.yml up --build
```

The overlay is opt-in on purpose: a plain `docker compose up` never picks it up.

Verify everything is healthy:

```bash
docker compose ps
curl http://localhost:8080/api/rag/health
curl http://localhost:8080/api/llm/health
```

`nginx` is the **only** published port, and it listens on `127.0.0.1` by default.
To reach the stack from other machines on your network, set `GATEWAY_BIND=0.0.0.0`
in `.env`. The APIs need a session or an API key, but registration stays open
until you set `ALLOW_REGISTRATION=false`. If `docker compose ps` shows services
as `Exited`, nothing is listening on `:8080` and the whole UI — not just
RAG — will be unreachable; see [Troubleshooting](#troubleshooting).

## 4. Open the chat UI

Go to **http://localhost:8080** and create an account. The chat app is the
`web` container (Next.js), served through the nginx gateway.

- **Model:** pick one at the top right. The list comes from rag-service's
  `/v1/models`: your local Ollama models, plus any cloud models whose keys are
  set in `.env`.
- Every answer is grounded in whatever you have indexed (step 5), and streams
  as it is written.

[usage.md](usage.md) covers day-to-day use: adding documents, what to expect
from answers, and letting other people on your network sign in.

## 5. Index a PDF

Upload through the API; the chat app has no upload button yet
([#15](https://github.com/sameeralam3127/llm-dev-kit/issues/15)). Create an API
key first: account menu → **API keys**. The file is chunked, embedded locally,
and indexed into ChromaDB:

```bash
KEY=sk-ldk-...   # your key
curl -X POST http://localhost:8080/api/rag/ingest/pdf \
  -H "Authorization: Bearer $KEY" -F "file=@mydoc.pdf"
# {"chunks": 12}
```

Then just chat — relevant chunks are retrieved automatically. Useful checks
(these two need the admin role, which the first account has):

```bash
# how many chunks are currently indexed
curl http://localhost:8080/api/rag/documents/stats -H "Authorization: Bearer $KEY"

# wipe the PDF index
curl -X POST http://localhost:8080/api/rag/documents/clear -H "Authorization: Bearer $KEY"
```

The PDF must contain selectable text — scanned image pages produce zero
chunks and a 400 response.

## 6. Cloud models (optional)

Cloud calls are routed through LiteLLM. Set `OPENAI_API_KEY`,
`GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY` in `.env` to make those models
available to everyone in the model picker, or pass `api_key` per request to
`/api/rag/chat`. The chat app has no field for a personal cloud key. See the
README's [Configuration section](../README.md#configuration) for details.

## Reaching Redis or Chroma from the host

Redis and Chroma are deliberately not published: the services reach them over
the Compose network, and neither has authentication. To inspect them from your
machine while debugging, create a local override file (not committed), bound
to localhost only:

```yaml
# compose.debug-ports.yml
services:
  redis:
    ports: ["127.0.0.1:6379:6379"]
  chroma:
    ports: ["127.0.0.1:8000:8000"]
```

```bash
docker compose -f docker-compose.yml -f compose.debug-ports.yml up -d redis chroma
```

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
ruff check services tests && ruff format --check services tests
mypy
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

The Chroma plugin's contract suite needs a real Chroma, which CI runs; locally
it is skipped unless you start one:

```bash
docker run -d -p 127.0.0.1:8000:8000 chromadb/chroma:1.5.9
LDK_TEST_CHROMA_HOST=localhost python3 -m pytest tests/plugins/test_chroma_plugin.py
```

The web app's checks, from `web/`:

```bash
npm run typecheck && npm run lint && npm test && npm run build
npm run bench    # streaming render cost, before and after (not part of CI)
```

CI runs all of these on every push and pull request; images are published only
after it passes.

## Published images

Every push to `main` publishes each service as its own image to GitHub
Container Registry, tagged `latest` and by commit SHA, once CI passes. A
version tag such as `v2.0.0` would also publish `2.0.0`, `2.0` and `2`; none
has been tagged yet.

```bash
docker pull ghcr.io/sameeralam3127/llm-dev-kit-gateway:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-web:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-llm-service:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-rag-service:latest
docker pull ghcr.io/sameeralam3127/llm-dev-kit-mcp-service:latest
```

`docker-compose.yml` still builds locally by default; the images are for running
the stack elsewhere without a build.

## Scaling rag-service

`rag-service` runs 2 replicas by default (`deploy.replicas` in
`docker-compose.yml`); Nginx round-robins across them via Docker's embedded
DNS. To change the replica count at runtime:

```bash
docker compose up -d --scale rag-service=4
```

Nginx re-resolves the service name every 10 seconds, so new replicas get
traffic without a restart.

## Troubleshooting

- **Nothing loads at `localhost:8080` / "RAG option" missing entirely** —
  run `docker compose ps`. If containers show `Exited`, the stack isn't
  running (Docker Desktop restart, host sleep, or a manual `down`/`stop` are
  the usual causes) — bring it back with `docker compose up -d` and re-check
  `docker compose ps` for `healthy` status.
- **"no local models found" in the model picker** — check Ollama is running
  (`ollama list`) and reachable from Docker. Compose defaults to
  `http://host.docker.internal:11434`. A `.env` with `OLLAMA_HOST=http://localhost:11434`
  (the value for services run outside Docker) points the container at itself:
  change that line back to `http://host.docker.internal:11434`.
- **The app can't be reached from another machine** — expected: the gateway
  binds to `127.0.0.1`. Set `GATEWAY_BIND=0.0.0.0` in `.env` (with
  `ALLOW_REGISTRATION=false`) and run `docker compose up -d`.
- **`401` from the APIs** — the call has no personal API key, or the key
  was revoked: send `Authorization: Bearer sk-ldk-...` (account menu → API
  keys). `403` means the key's role cannot do that (only `user` and `admin`
  ingest; only `admin` clears). See [MIGRATION.md](v2/MIGRATION.md).
- **Cloud model errors** — `401` with a message about the provider means its
  key is missing or invalid: set it in `.env` or pass `api_key` per request.
- **PDF retrieval returns nothing** — the PDF must contain selectable text,
  not scanned images; confirm chunks were actually indexed with the admin
  key: `curl http://localhost:8080/api/rag/documents/stats -H "Authorization: Bearer $KEY"`.
- **`docker compose up` fails with "required variable AUTH_SECRET is
  missing"** — expected: the session key has no default. Run
  `echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env`.
- **A Python service exits with `Invalid environment configuration:`** — the
  message lists every bad variable; fix those in `.env` or the compose
  environment.
- **llm-service exits with `Unknown embedding dimension for Ollama model …`**
  — `DEFAULT_EMBEDDING_MODEL` is a model llm-service does not know; set
  `EMBEDDING_DIMENSION` to its vector length.
- **Logs show `plugin skipped` at startup** — an installed plugin failed to
  load; the line names the entry point and the reason. The service keeps
  running without it.
