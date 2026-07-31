---
name: smoke-test
description: "End-to-end verification of the web chat app: build, seed, sign in, exercise chats/folders/streaming/edit/regenerate/share, and prove failure paths (model host down, partial answers persisted). Use after any change to the chat path, before declaring a phase done, or when something 'works locally' needs proof."
---

# Smoke test — prove the chat path works

Run this after touching anything on the send/stream/persist path, and always
before marking a roadmap phase complete. It verifies behaviour, not just
compilation.

## 0. Build gate

```bash
cd web && npx tsc --noEmit && npm run lint && npm run build
```

Any failure stops here.

## 1. Stand up app + mock model

Use a mock OpenAI-compatible server so the test is deterministic and free.
Write it to the scratchpad (a `node:http` server answering `/v1/models` and
`/v1/chat/completions` with a few SSE deltas — split at least one frame
across two writes to prove the parser buffers). Then:

```bash
npm run db:push && npm run db:seed        # demo@example.com / demo-password-1
node <scratchpad>/mock-llm.mjs &          # e.g. port 3222
PORT=3111 LLM_BASE_URL=http://localhost:3222/v1 npm run start &
```

## 2. Auth

```bash
CSRF=$(curl -s -c cj.txt localhost:3111/api/auth/csrf | sed 's/.*"csrfToken":"\([^"]*\)".*/\1/')
curl -s -b cj.txt -c cj.txt -X POST localhost:3111/api/auth/callback/credentials \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "csrfToken=$CSRF" \
  --data-urlencode "email=demo@example.com" \
  --data-urlencode "password=demo-password-1" \
  --data-urlencode "callbackUrl=http://localhost:3111/"
curl -s -b cj.txt localhost:3111/api/auth/session   # expect user.id present
```

Also check the negative: `/api/chats` with **no** cookie must return 401 JSON,
and `/` must 307 to `/login`.

## 3. Core flows (all authenticated with `-b cj.txt`)

| Check | How | Pass condition |
| --- | --- | --- |
| Models | `GET /api/models` | mock's models listed, grouped by provider |
| Create chat | `POST /api/chats {}` | 201, id returned |
| Stream | `POST /api/chat {chatId, intent:"send", content:…}` with `-N` | `meta` → `delta`s → `done`; title auto-derived |
| Regenerate | `intent:"regenerate"` | old answer archived: assistant message has `versions: [1]` |
| Edit | `intent:"edit", targetMessageId, content` | history REWOUND (message count unchanged), `editedAt` set, prior content in versions |
| Folders | create/move/delete | delete keeps chats (folderId → null) |
| Share | `PATCH {shared:true}` → GET `/share/<id>` no cookie | content visible; after `{shared:false}` the link 404s |
| Validation | bad folder color, empty name | 400 with per-field details |

## 4. Failure paths — the part most tests skip

1. **Kill the mock model server.** Send a turn: expect a `meta` frame then an
   `error` frame (`upstream_unavailable`), and afterwards `GET` the chat —
   the user message must exist and the assistant row must carry
   `error` + `truncated:true`. A failed turn must never eat the user's text.
2. **Abort mid-stream** (`curl --max-time 1` on a slow mock): the partial
   content must be persisted with `truncated:true` and **no** error.

## 5. Clean up

Stop background servers, then reset the DB to a clean seeded state:

```bash
rm -f web/prisma/dev.db && cd web && npm run db:push && npm run db:seed
```

## Reporting

State plainly what passed and what failed with the actual output — never
"should work". If a check cannot be run (e.g. Docker not available), say so
explicitly rather than skipping silently.
