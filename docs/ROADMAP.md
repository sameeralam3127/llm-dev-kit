# LLM Dev Kit — AI Chat Roadmap

The project grows in phases. Each phase is production-ready before the next
begins, and each lands as a **hot-pluggable module** behind an interface, so
you can learn one concept at a time without destabilising what already works.

Use the `/roadmap` skill in Claude Code to see where the project is, plan the
next increment, and get a guided implementation with learning notes.

## How to read this document

Each phase lists its goal, its features, and its **seam** — the interface it
plugs into. The seam is the important part: it is what keeps the module
swappable and the learning incremental.

---

## Phase 1 — Foundation ✅ (complete)

A production chat application: Next.js 15, TypeScript, Tailwind, shadcn/ui.

- Auth (email/password + optional GitHub OAuth), JWT sessions
- Multiple sessions, persistent history, folders, rename/pin/archive/delete
- Streaming with stop; partial answers always persisted
- Edit-with-rewind, regenerate with version history
- Markdown, syntax highlighting, copy/share, responsive, accessible

**Seam established:** `ChatProvider` (`web/src/lib/llm/types.ts`) — everything
that generates tokens sits behind this interface.

## Phase 2 — Multi-Model AI 🚧 (next)

Support every major LLM host: OpenAI, Anthropic, Gemini, Groq, OpenRouter,
Ollama, LM Studio, Azure OpenAI.

- Per-provider adapters implementing `ChatProvider`
- Provider/model switching in the UI; sampling params (temperature, top-p,
  max tokens, penalties)
- Retry with backoff, token counting, cost estimation, automatic fallback

**Seam:** `ChatProvider` already exists — this phase is adapters plus a
registry that routes `provider/model` ids. Use the `/add-provider` skill.

## Phase 3 — Memory

ChatGPT-like memory: conversation, user, workspace, global tiers; automatic
extraction, vector search, ranking, summarisation, expiry, a memory UI.

**Seam:** a `MemoryStore` interface consulted at prompt-build time; Postgres +
pgvector replaces SQLite when this lands.

## Phase 4 — RAG 2.0

Enterprise document assistant: PDF/DOCX/PPT/XLSX/CSV/Markdown, GitHub,
websites, YouTube, Notion, Confluence. OCR → chunk → embed → hybrid search
(BM25 + dense) → rerank → answer with citations and source highlighting.

**Seam:** the existing `rag-service` pipeline, upgraded stage by stage — each
stage (chunker, retriever, reranker) behind its own interface.

## Phase 5 — AI Agents

Planner / executor / reflection loops, tool selection, retries, task graphs.
Tools: GitHub, Gmail, Calendar, Slack, terminal, database, web search,
browser, filesystem. MCP-compatible.

**Seam:** the existing `mcp-service`, plus a `Tool` interface with a
permission layer.

## Phase 6 — Coding Assistant

Repository indexing, AST parsing, semantic code search, dependency graphs,
PR review, refactoring, test generation, architecture visualisation.

## Phase 7 — Workspace

Projects, notes, documents, tasks, canvas — all searchable, all referenceable
by the AI.

## Phase 8 — Voice AI

WebRTC, streaming STT/TTS, interruption, low latency, multiple voices.

## Phase 9 — Image & Video AI

Image generation and editing, vision, OCR, video and screen understanding.

## Phase 10 — Enterprise

Teams, organisations, RBAC, audit logs, billing, API keys, usage analytics,
SSO, SCIM. Multi-tenant.

## Phase 11 — AI Intelligence Layer

Intent detection, automatic model routing, tool orchestration, context
compression, self-evaluation, hallucination detection, confidence scoring.

---

## Target architecture

```text
                    User
                      │
                Next.js Frontend        (web/)
                      │
              API Gateway / BFF          (nginx + web API routes)
                      │
             AI Orchestration Layer      (Phase 11)
      ┌───────────────┼────────────────┐
      │               │                │
  LLM Router      Memory Engine     Agent System
  (Phase 2)       (Phase 3)         (Phase 5)
      │               │                │
      └──────┬────────┴────────┬───────┘
             │                 │
        RAG Pipeline      MCP Tool Manager
        (Phase 4)         (mcp-service)
             │                 │
      Vector Database     External Services
             │
   PostgreSQL + pgvector   (Phase 3+)
```

## Working agreement

1. **One phase at a time.** A phase is done when it is typechecked, built,
   smoke-tested (`/smoke-test`), and documented.
2. **Everything behind a seam.** New capability = new interface + first
   implementation, never a hard-wired dependency.
3. **Learning first.** Each phase should leave behind notes on *why* the
   design is shaped the way it is, not only working code.
