# LLM Dev Kit

A local-first AI chat platform built as a **learning journey**: it grows in
phases (see `docs/ROADMAP.md`), each landing as a hot-pluggable module behind
an interface, production-ready before the next begins.

## Layout

- `web/` — the frontend: Next.js 15 + TypeScript + Tailwind + shadcn/ui,
  Prisma (SQLite, Postgres-ready), Auth.js. See `web/README.md`.
- `services/` — Python microservices: `rag_service` (RAG chat + OpenAI-compatible
  `/v1`), `llm_service` (model routing: Ollama + cloud via LiteLLM),
  `webhook_service`, `embedding_worker`, `mcp_service`.
- `nginx/` — the gateway; the only published port (8080). Routes `/v1/`,
  `/api/rag/`, `/api/llm/`, `/webhooks/` to Python services, everything else
  to `web`.
- `docs/ROADMAP.md` — the 11-phase plan and each phase's seam.

## Skills

Skills live in `.claude/skills/` which is **local-only (gitignored, never
pushed)**: `/roadmap` (plan the next learning increment), `/add-provider`
(new LLM host), `/add-feature` (standard web/ layering), `/smoke-test`
(end-to-end proof).

## Working agreement

1. **One increment at a time, verified.** Typecheck + build always;
   `/smoke-test` for anything on the chat path. A phase is done only when
   proven, not when it compiles.
2. **Everything behind a seam.** Token generation goes through `ChatProvider`
   (`web/src/lib/llm/types.ts`); DB mutation and ownership checks live only in
   `web/src/server/services/`; routes parse → delegate → serialise.
3. **Teach while building.** This repo exists to learn from: leave short
   why-this-design notes in the relevant phase of `docs/ROADMAP.md`, and keep
   code comments to constraints the code cannot express itself.
4. **Keep the schema portable.** No Prisma enums/Json/scalar lists — the
   SQLite → Postgres switch must stay a one-word change.
5. **Secrets never ship.** `AUTH_SECRET` has no default anywhere; `.env` is
   gitignored; build-time placeholders stay inline on RUN commands.

## Commands

```bash
# full stack (needs AUTH_SECRET in .env — openssl rand -base64 32)
docker compose up --build              # http://localhost:8080

# web app alone, against any OpenAI-compatible /v1
cd web && npm run dev                  # http://localhost:3000
npm run typecheck && npm run lint && npm run build   # the gate

# python services
pytest tests/
```
