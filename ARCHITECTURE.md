# Architecture

LLM Dev Kit is evolving from the runnable v1 Compose stack to the v3 secure,
workspace-aware architecture. Both code paths are in this repository, but only
the v1 stack is currently wired into `docker-compose.yml`. The distinction is
intentional: do not deploy the v3 services until roadmap step g supplies the
v3 Compose profile, secrets, network isolation, and end-to-end tests.

| | Current runnable stack (v1) | v3 target |
| --- | --- | --- |
| Entry point | Nginx on `:8080` | Edge proxy, the only published port |
| Chat and retrieval | `rag-service` + Redis + Chroma | `core-api` + Postgres/pgvector |
| Model access | `llm-service` | `model-gateway`, the only model caller |
| Ingestion | HTTP path in `rag-service` | `ingest-worker` over a Postgres job queue |
| Identity and tenancy | Auth.js, per-user chat history in SQLite | Signed identity plus workspace-scoped access in Postgres |
| Network policy | Compose default network | Internal network; model gateway is the controlled egress point |

## Current runnable stack (v1)

`docker compose up` starts the following architecture. Nginx is the only
published service and binds to `127.0.0.1:8080` unless `GATEWAY_BIND` is set.

```mermaid
flowchart LR
  B[Browser / OpenAI SDK] --> N[Nginx :8080]
  N --> W[web\nNext.js 16, Auth.js, SQLite]
  N --> R[rag-service\nRAG and OpenAI API]
  N --> L[llm-service\nmodel routing]
  R --> C[(ChromaDB)]
  R --> RD[(Redis cache)]
  R --> L
  L --> O[Ollama]
  L -. optional cloud providers .-> CP[OpenAI / Gemini / Anthropic]
  M[MCP client] --> MS[mcp-service]
  MS --> R
  MS --> L
```

### Routing

| Public path | Upstream |
| --- | --- |
| `/` and web-owned `/api/*` routes | `web` |
| `/v1/*` and `/api/rag/*` | `rag-service` |
| `/api/llm/*` | `llm-service` |
| `/sso/*` with the SSO profile | Keycloak |

Nginx disables proxy buffering for streaming responses. Its frontend-only
startup page handles a temporarily unavailable `web` container; API routes
retain their real upstream status codes.

## v3 target architecture

The v3 services and their migrations are implemented in the repository, but
they are not yet in the default Compose file. Their contract is defined in
[the v3 roadmap](docs/v3/ROADMAP.md).

```mermaid
flowchart LR
  B[Browser] --> E[edge\nonly published port]
  SDK[SDK / API key] --> E
  E --> W[web\nNext.js + identity]
  E --> C[core-api\nauth, workspaces, chat, retrieval]
  W -->|signed user identity| C
  C --> PG[(Postgres 16 + pgvector)]
  C -->|model request| G[model-gateway]
  I[ingest-worker] -->|claim jobs| PG
  I -->|embeddings| G
  G -->|audit event| PG
  G --> O[Ollama]
  G -. refused in sovereign mode .-> CL[Cloud model providers]

  subgraph internal [internal network]
    W
    C
    I
    PG
    O
  end
```

### v3 responsibilities

- **core-api** authenticates sessions and workspace API keys, resolves every
  request to user, workspace, and scopes, performs hybrid retrieval, and
  serves `/v1/models` and `/v1/chat/completions` over SSE.
- **ingest-worker** claims Postgres jobs with `FOR UPDATE SKIP LOCKED`, parses
  PDFs, chunks them, requests embeddings, and atomically replaces a document's
  chunks.
- **model-gateway** authenticates internal callers, applies sovereign-mode
  egress rules before a model request, and records each permitted request in
  the audit log.
- **Postgres with pgvector** is the system of record for workspaces, API keys,
  documents, jobs, chunks, provenance, and audit events. Retrieval filters by
  `workspace_id` in SQL.

## Operational boundaries

- Every currently public endpoint goes through Nginx; backend data services
  are not published as host ports.
- v3 makes authentication and workspace authorization mandatory for `/api/*`
  and `/v1/*`. A personal workspace API key is stored as a prefix plus a
  server-peppered HMAC, never plaintext.
- `SOVEREIGN_MODE=true` is the v3 default. It prevents cloud providers and
  Ollama cloud-model identifiers before any prompt can leave the network.
- The v3 Compose profile will run internal containers on an `internal: true`
  network and use Docker secrets, read-only filesystems, healthchecks, image
  scanning, and an SBOM before it is considered deployable.
