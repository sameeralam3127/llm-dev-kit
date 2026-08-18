# Web — AI Chat Application

A production-ready chat front end for LLM Dev Kit: Next.js 15 (App Router),
React 19, TypeScript, Tailwind CSS and shadcn/ui components.

It talks to **any OpenAI-compatible `/v1` endpoint**. By default that is this
repo's `rag-service`, so answers come back grounded in your indexed PDFs and
GitHub docs — but the same build works against raw Ollama or a hosted API by
changing one environment variable.

> This is the project's frontend. It replaced the earlier static `ui/`
> (React + Vite) page, which was removed — nginx now reverse-proxies this app
> at `/` instead of serving files from disk.

## Quick start

```bash
cd web
npm install
cp .env.example .env          # then set AUTH_SECRET
openssl rand -base64 32       # paste into AUTH_SECRET

npm run db:push               # create the SQLite schema
npm run db:seed               # optional demo account + example chat
npm run dev                   # http://localhost:3000
```

The seed creates `demo@example.com` / `demo-password-1`.

Point `LLM_BASE_URL` at a running backend:

| Backend | Value |
| --- | --- |
| rag-service directly | `http://localhost:8020/v1` |
| via the nginx gateway | `http://localhost:8080/api/rag/v1` |
| Ollama directly | `http://localhost:11434/v1` |

## Features

**Conversations** — multiple sessions, persistent history, folders with colours,
pin to top, rename, full-text search across titles and message bodies.

**Messages** — token-by-token streaming with a stop button; edit a message to
rewind the conversation and regenerate from that point; regenerate an answer
while keeping the previous one reachable through a `‹ 2/3 ›` control; copy a
message, copy a deep link to it, or publish the whole chat as a revocable
read-only link.

**Rendering** — GitHub-flavoured Markdown, syntax-highlighted code blocks with
per-block copy and soft-wrap toggle, tables that scroll instead of breaking the
layout.

**Accessibility** — keyboard reachable throughout, visible focus rings, skip
link, labelled landmarks and live regions, `prefers-reduced-motion` respected,
zoom not disabled. Screen readers get one "loading conversation" announcement
rather than one per skeleton block.

## Architecture

```
src/
├── app/
│   ├── (auth)/                 sign-in and registration
│   ├── (chat)/                 authenticated shell + chat pages
│   ├── share/[shareId]/        public read-only view
│   ├── api/                    route handlers
│   ├── error.tsx               route-level error boundary
│   └── global-error.tsx        root-layout crash fallback
├── components/
│   ├── ui/                     shadcn primitives
│   ├── chat/  sidebar/  markdown/  auth/  layout/  skeletons/
│   └── error-boundary.tsx      subtree boundary for smaller pieces
├── hooks/                      streaming, data fetching, clipboard, scroll
├── lib/
│   ├── llm/                    provider adapter + SSE parser
│   ├── auth/                   edge-safe config split from Node adapter
│   ├── validations/            Zod schemas shared by client and server
│   └── api-client.ts           typed fetch wrapper
├── server/                     services, DTO mappers, HTTP helpers
├── stores/                     Zustand UI state
└── types/                      domain and protocol types
```

Three boundaries do most of the work:

**`ChatProvider`** (`lib/llm/types.ts`) is the seam to the model host. Swapping
backends means writing one adapter, not touching routes or components.

**Services** (`server/services/`) own every ownership check and all history
mutation. Route handlers only parse, delegate and serialise — no handler
queries the database directly.

**The stream protocol** (`types/chat.ts`) is a discriminated union of `meta`,
`delta`, `done` and `error` frames, so client and server cannot drift.

### Streaming

`POST /api/chat` opens a `text/event-stream`. Failures before the stream opens
come back as normal JSON errors; once it is open, they arrive as an `error`
frame — the client only handles one shape.

Two details that matter in practice:

- **Partial answers are never lost.** Whether the user hits Stop, the tab
  closes, or the model host dies mid-sentence, whatever was generated is written
  to the database in the stream's `finally` path. A cancelled generation is
  recorded as `truncated`, not as an error, because stopping was a choice.
- **Tokens are batched per animation frame.** A fast local model emits far more
  tokens than the screen can paint; committing each one individually turns into
  hundreds of renders a second.

`X-Accel-Buffering: no` is set because nginx buffers proxied responses by
default, which would silently defeat streaming behind the gateway.

### Edit and regenerate

Editing a message or regenerating an answer **rewinds** the conversation:
everything after that point is deleted, because a reply the user rewound past
can no longer be consistent with what follows it. The content being replaced is
archived to `MessageVersion` first, so nothing is destroyed — the UI pages
through previous answers instead of losing them.

### Database

Prisma with SQLite by default: no setup, file-backed, survives restarts. The
schema deliberately avoids enums, `Json` and scalar lists, so moving to Postgres
is a one-word change:

```prisma
datasource db {
  provider = "postgresql"   // was "sqlite"
  url      = env("DATABASE_URL")
}
```

Roles and folder colours are stored as strings and narrowed back to union types
in `server/mappers.ts`.

### Auth

Auth.js v5 with JWT sessions. `lib/auth/config.ts` is the edge-safe half —
no Prisma, no bcrypt — so `middleware.ts` stays deployable to the edge runtime;
`lib/auth/index.ts` adds the Prisma adapter and the credentials provider.

Sign-in compares against a dummy hash when no user exists, so a wrong email and
a wrong password take the same time and the endpoint does not leak which
addresses are registered. `callbackUrl` is restricted to same-origin relative
paths to prevent an open redirect. GitHub OAuth registers itself only when both
`AUTH_GITHUB_ID` and `AUTH_GITHUB_SECRET` are present.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Development server |
| `npm run build` | Generate Prisma client, then production build |
| `npm run start` | Serve the production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint |
| `npm run db:push` | Apply the schema without a migration |
| `npm run db:migrate` | Create and apply a migration |
| `npm run db:seed` | Demo account and example chat |
| `npm run db:studio` | Prisma Studio |

## Environment

| Variable | Required | Default | Notes |
| --- | :---: | --- | --- |
| `DATABASE_URL` | ✓ | `file:./dev.db` | |
| `AUTH_SECRET` | ✓ | — | ≥ 32 chars; `openssl rand -base64 32` |
| `AUTH_URL` | | `http://localhost:3000` | Public origin |
| `LLM_BASE_URL` | | `http://localhost:8080/api/rag/v1` | OpenAI-compatible `/v1` |
| `LLM_API_KEY` | | `sk-local` | `sk-local*` keeps rag-service offline |
| `DEFAULT_MODEL` | | `llama3.1` | |
| `LLM_REQUEST_TIMEOUT_MS` | | `120000` | |
| `ALLOW_REGISTRATION` | | `true` | `false` locks to existing users |
| `AUTH_GITHUB_ID` / `AUTH_GITHUB_SECRET` | | — | Both needed to enable OAuth |

Configuration is validated with Zod at startup (`lib/env.ts`), so a missing or
malformed value fails immediately with a readable message rather than surfacing
as a 500 in the middle of a stream.

## Running in the compose stack

The app is a core service in the root `docker-compose.yml` — no overlay needed:

```bash
cp .env.example .env
echo "AUTH_SECRET=$(openssl rand -base64 32)" >> .env
docker compose up --build
```

It is reached through the nginx gateway on **http://localhost:8080**, not
directly — the container publishes no host port of its own. Inside the network
it talks to `rag-service:8020` directly rather than looping back out through
nginx, and its SQLite file lives on the `web_data` volume so history survives
container replacement.

nginx routes by longest-prefix match: `/v1/`, `/api/rag/`, `/api/llm/` and
`/webhooks/` go to the Python services, and everything else — including this
app's own `/api/auth`, `/api/chat`, `/api/chats`, `/api/folders` and
`/api/models` — falls through to `location /`. The gateway's existing
`proxy_buffering off` is what allows SSE tokens through in real time.

## Production notes

Before putting this in front of real users:

- **Rate limiting is per-process.** `server/rate-limit.ts` is an in-memory
  fixed-window limiter — enough to blunt credential stuffing on a single
  instance. Behind more than one replica it becomes per-replica; move it to
  Redis (the compose stack already runs one) before treating it as a quota.
- **Move off SQLite** for concurrent writers. See the one-word change above.
- **Set `AUTH_SECRET` to a real random value.** The committed `.env` is a
  development placeholder.
