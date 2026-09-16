# LLM Dev Kit — v2 Roadmap

v2 is the path from today's chat app to a private, self-hostable AI assistant
for teams: company sign-in, retrieval that respects who may see which
document, tools over MCP, and an admin portal.

It is **not a rewrite**. Each step lands in this repository, follows the
working agreement in [ROADMAP.md](ROADMAP.md) (one phase at a time, everything
behind a seam, learning first), and maps onto an existing roadmap phase.

## Principles

1. **Evolve, don't replace.** The Next.js + Prisma + Auth.js app stays. New
   capability arrives behind the seams it already has (`ChatProvider`, and the
   `MemoryStore`, retriever and `Tool` interfaces the later phases introduce).
2. **Permissions live in the data layer.** Document visibility is enforced in
   SQL, never in the prompt. A prompt can never widen what a user may see.
3. **Local by default.** No request leaves the machine unless an administrator
   adds a cloud model.
4. **Add infrastructure when load demands it.** Replicas, a dynamic load
   balancer and Kubernetes come after there is traffic to justify them.
5. **Small enough to run on a laptop.** `docker compose up` should stay usable
   on 8–16 GB of RAM.

## Open decision: one backend language

Chat currently runs through Next.js API routes, while RAG and MCP are Python
services. Before Phase 4, decide deliberately:

| Option | For | Against |
|---|---|---|
| TypeScript-first (Next.js routes own the API) | One language, reuses Phase 1 code | Weaker RAG/agent ecosystem |
| Python backend (FastAPI + LangGraph) | Best RAG, agent and MCP libraries | Two runtimes; chat routes must move |
| Hybrid (Next.js for app, Python for RAG/agents behind HTTP) | Keeps both strengths; matches today | Two deploy targets, cross-service auth |

Record the choice as an ADR in `docs/`.

---

## Step 0 — Security fixes (now, before anything else)

- Remove `allowDangerousEmailAccountLinking: true` from
  `web/src/lib/auth/index.ts`; link accounts only on a verified email.
- Stop publishing Redis (6379), Chroma (8000) and Ollama (11434) on host ports
  in `docker-compose.yml`. Only the gateway publishes a port.
- Require a password on Redis; no default secrets anywhere.
- Add a CI gate: tests, typecheck, lint and dependency audit must pass before
  images are published to GHCR.

**Done when:** a port scan of the host shows only the gateway, and CI blocks a
failing build from publishing.

## Step 1 — Multi-model (Phase 2)

- Hand-written `ChatProvider` adapters for the main hosts (the learning goal).
- A LiteLLM adapter as one more provider, giving a catalog, virtual keys and
  spend tracking without writing every adapter.
- Model registry routing `provider/model` ids; model switcher in the UI.

**Seam:** `ChatProvider` (`web/src/lib/llm/types.ts`).

## Step 2 — Postgres + pgvector (Phase 3)

- Replace SQLite with Postgres (Prisma supports both; migrate with
  `prisma migrate`).
- Enable pgvector. Conversation memory behind a `MemoryStore` interface.
- Redis for shared rate limits and cache, replacing in-memory limiters.

**Seam:** `MemoryStore`, consulted at prompt-build time.

**Watch out:** a `vector(N)` column fixes the embedding dimension. Changing the
embedding model is a migration plus a full re-embed, so store the model name
with each chunk.

## Step 3 — Knowledge with access control (Phase 4)

- Tables: `collections`, `collection_grants` (collection, group, permission),
  `documents` (with `active_version`), `chunks` (document, version, content,
  metadata, excluded flag, embedding).
- Upload → parse in a worker → automatic chunking → embed → index. Switching
  to a new version happens in one transaction.
- **Chunk preview** (optional, not the default path): see chunk boundaries,
  adjust size/overlap, exclude boilerplate, then re-index.
- Retrieval filters by the user's groups in SQL. Use `EXISTS`, not a join, so
  users in several groups do not get duplicate chunks:

  ```sql
  SELECT c.id, c.content, c.metadata, d.title
  FROM   chunks c
  JOIN   documents d ON d.id = c.document_id AND d.active_version = c.version
  WHERE  NOT c.excluded
    AND  EXISTS (
           SELECT 1 FROM collection_grants g
           WHERE  g.collection_id = d.collection_id
             AND  g.group_name = ANY(:user_groups))
  ORDER  BY c.embedding <=> :query_embedding
  LIMIT  :k;
  ```

  Check the plan with `EXPLAIN ANALYZE`; with pgvector 0.8+ set
  `hnsw.iterative_scan` so filtering does not destroy recall.
- Response cache key includes the model, the conversation, the user's
  readable collection ids and those collections' versions. Turns that call
  tools are never cached.
- Retire Chroma.
- Later in the phase: hybrid search (full-text + vectors), reranking,
  citations.

**Seam:** chunker, retriever and reranker interfaces, each pluggable.

## Step 4 — Tools and integrations (Phase 5)

- MCP server registry (URL, auth, enabled) managed by admins; tools granted
  per role.
- Tools that change data require user confirmation in the chat.
- Retrieved text and tool output are treated as data, never as instructions.
- Expose the assistant to other programs: OpenAI-compatible `/v1` with
  personal API keys (hashed at rest), and an MCP endpoint with
  `search_knowledge`, `ask` and `list_collections`.

**Seam:** `Tool` interface with a permission layer, plus the `mcp-service`.

## Step 5 — Enterprise identity and admin (Phase 10)

- SSO through Auth.js OIDC providers (Google, Okta, Entra ID). Introduce
  Keycloak only when brokering several SAML/OIDC identity providers is needed.
- Roles: `viewer`, `member`, `knowledge_admin`, `platform_admin`, mapped to
  permissions in one table; every route declares the permission it needs.
- Admin portal at `/admin`: people and roles, collections and grants, models
  and budgets, MCP tools, usage, audit log, system health.
- Append-only audit log for sign-ins, permission changes, uploads, deletions,
  tool calls and API key use.

## Step 6 — Production hardening

- TLS overlay (`compose.prod.yml`) with Let's Encrypt; GPU overlay for Ollama.
- `scripts/init.sh` generates secrets on first run; `Makefile` targets for
  `init | up | down | logs | test | backup`.
- Nightly `pg_dump` plus WAL archiving; restore tested in CI.
- OpenTelemetry tracing (Langfuse optional), load tests.

## Deferred until load requires it

| Item | Add it when |
|---|---|
| Traefik (replacing nginx) | Running multiple API replicas that come and go |
| Postgres read replica | Reads measurably bottleneck on a separate host |
| Automatic DB failover (Patroni, CloudNativePG, managed) | Uptime matters more than simplicity |
| Helm chart | Deploying to Kubernetes |
| Qdrant or a dedicated vector store | Tens of millions of chunks or slow retrieval |
| vLLM or managed inference | Many concurrent users on local models |
| Separate worker queues per job type | Large uploads delay small ones |
| Multi-tenant isolation | Hosting more than one organisation |

## What carries over

The `ChatProvider` interface, partial-answer persistence on stop, the chat UI
components (Markdown, code blocks, version switcher, share dialog), and the
chunking and cache-key tests. Retired over time: the custom `llm-service`
(if LiteLLM covers it), Chroma, SQLite, and in-memory rate limiting.
