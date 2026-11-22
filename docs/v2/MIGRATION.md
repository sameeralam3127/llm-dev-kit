# Migrating to v2

The breaking changes, in the order they land, and what to do about each. Each
section says which phase introduced it; everything else in v2 is additive.

## Phase 4 — Authentication: the `/v1` break

### What changed

Until now, anyone who could reach the gateway could call every API: chat,
`/v1`, PDF ingest, even clearing the index. Now every API call needs a
credential, and the Python services check it themselves rather than trusting
the gateway.

| | Before | Now |
| --- | --- | --- |
| `/v1/*`, `/api/rag/*`, `/api/llm/*` without a credential | works | **401** `unauthorized` |
| `Authorization: Bearer …` on `/v1` | a cloud provider key to spend on this request | **who you are**: a personal API key or an access token |
| `/api/rag/ingest/pdf` | anyone | role `user` or `admin` |
| `/api/rag/documents/*`, `/api/rag/cache/*` | anyone | role `admin` |
| `/api/rag/health`, `/api/llm/health` | public | still public |
| The web app's chat | unchanged | unchanged; it sends each user's own token behind the scenes |

Request and response bodies, paths and the SSE framing are unchanged, so any
OpenAI SDK keeps working once it has a key.

**Roles.** Every account has one:

| Role | Can |
| --- | --- |
| `viewer` | chat, list models |
| `user` | the above, and add documents |
| `admin` | the above, and clear the index and the cache |

The first account ever registered becomes the admin. On an existing install,
the earliest account is promoted when the web app starts. Everyone else is a
`user`. An admin changes roles under account menu → **Admin** → **Users**.

### What to do

1. **Upgrade** as usual: `git pull`, then `docker compose up -d --build`.
2. **Create an API key** for each script or client: in the web app, open the
   account menu (bottom left) → **API keys** → **Create**. The key
   (`sk-ldk-…`) is shown once. It acts as you, with your role, until you
   revoke it.
3. **Send it as the Bearer token.**

   ```bash
   curl http://localhost:8080/v1/models -H "Authorization: Bearer sk-ldk-…"
   curl -X POST http://localhost:8080/api/rag/ingest/pdf \
     -H "Authorization: Bearer sk-ldk-…" -F "file=@handbook.pdf"
   ```

   ```python
   from openai import OpenAI
   client = OpenAI(base_url="http://localhost:8080/v1", api_key="sk-ldk-…")
   ```

4. **MCP**: set `LDK_API_KEY` to a key, in `.env` or in your MCP client's
   `env` (see `mcp.json`). Without it every tool call returns 401.
5. **Per-request cloud keys on `/v1` are gone.** The Bearer now says who you
   are, so it can no longer also carry an OpenAI or Gemini key. Put cloud keys
   in `.env` (`OPENAI_API_KEY`, …) so everyone can use those models. The
   `api_key` field in the body of `/api/rag/chat` still works as before;
   Phase 3 (sovereign mode) decides its future.
6. **If the web app talks to a third-party backend** (raw Ollama, a hosted
   API) through `LLM_BASE_URL`, keep `LLM_API_KEY` set to that backend's key.
   Against this repo's rag-service, leave it unset: the old `sk-local`
   placeholder now means "unset".

Revoking a key takes effect within a minute: each service caches a verified
key for at most 60 seconds.

### The escape hatch: `ALLOW_LEGACY_ANONYMOUS`

If you cannot update every client at once, set
`ALLOW_LEGACY_ANONYMOUS=true` in `.env` and run `docker compose up -d`. Until
**2.0.0** the old behaviour comes back:

- a call without a credential gets full access, as before;
- a Bearer that is not a personal key or an access token is treated as a
  cloud provider key on `/v1`, as before;
- a credential that *is* a key or token must still be valid.

Every anonymous request is logged as a warning. Because an anonymous caller is
an administrator, the services refuse to start with the setting on unless
`GATEWAY_BIND` is loopback (`127.0.0.1`, the default): it never faces a
network. The setting is **removed in 2.0.0**; plan to be off it by then.

### Accounts are no longer linked by email

GitHub sign-in used to attach itself to any local account with the same email
address (`allowDangerousEmailAccountLinking`). Whoever controlled a GitHub
account with your address could sign in as you. That is off. A GitHub or
single-sign-on login whose email already has an account now stops with a
message on the sign-in page. Sign in with that account's password instead.

### New, optional: single sign-on

`docker compose --profile sso up` adds Keycloak at `/sso` with a ready-made
realm. The settings are in the "Single sign-on" section of `.env.example`.
Keycloak users get an account in the web app on first sign-in, with the
`user` role.
