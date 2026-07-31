---
name: roadmap
description: "Learning-journey driver for LLM Dev Kit. Shows where the project is on the 11-phase roadmap (docs/ROADMAP.md), helps pick the next increment sized to what the user wants to learn, plans it against the existing seams, and guides implementation with learning notes. Use when the user asks 'what's next', wants to start/continue a phase, or asks how a phase should be designed."
---

# Roadmap — phase-wise learning driver

This project is a learning journey as much as a product. Your job is to help
the user advance it **one well-understood increment at a time**, never by
dumping a whole phase in one shot.

## Ground rules

1. **Read `docs/ROADMAP.md` first** — it is the source of truth for phases and
   their seams. Then check reality against it: a phase's status comes from the
   code, not the document (e.g. `ls web/src/lib/llm/` to see which providers
   actually exist).
2. **Size increments to learning.** Prefer "add retry-with-backoff to the
   provider adapter and understand why jitter matters" over "implement
   Phase 2". Ask what the user wants to learn if it is not obvious.
3. **Everything lands behind a seam.** Before writing code, name the interface
   the new capability plugs into (`ChatProvider`, a new `MemoryStore`, a
   `Tool`…). If no seam exists yet, designing it IS the first increment.
4. **Explain while building.** For each increment produce:
   - a short *why this design* note (2–5 sentences, trade-offs included)
   - the implementation
   - a verification step (typecheck + build at minimum; `/smoke-test` for
     anything touching the chat path)
5. **A phase is done** when it is typechecked, built, smoke-tested and its
   ROADMAP.md entry is updated (mark ✅, note any consciously-deferred gaps).

## Workflow

1. Determine current position: read ROADMAP.md, inspect the relevant code,
   summarise "you are here" in 3–4 sentences.
2. Propose 2–3 candidate next increments with effort estimates and what each
   teaches. Let the user pick (AskUserQuestion if interactive).
3. Plan the picked increment: files to touch, seam it plugs into, how to
   verify.
4. Implement, verify, then write the learning note into the phase's section
   of ROADMAP.md (or `docs/notes/phase-N.md` if it grows beyond a paragraph).
5. Update phase status markers (✅ / 🚧) honestly — partial is 🚧 with a list
   of what remains.

## Key seams (as of Phase 1)

| Seam | File | Plugs in |
| --- | --- | --- |
| `ChatProvider` | `web/src/lib/llm/types.ts` | token generation backends |
| Stream protocol | `web/src/types/chat.ts` (`StreamEvent`) | client/server framing |
| Services | `web/src/server/services/` | all DB mutation + ownership checks |
| RAG pipeline | `services/rag_service/` | retrieval, ingestion |
| MCP tools | `services/mcp_service/` | agent tools (Phase 5) |

## Do not

- Start a later phase while the current one has unverified pieces.
- Create per-phase skills preemptively — when a phase begins and a repeatable
  workflow emerges, add a skill for it then.
- Let "production-quality" mean "big": small, verified, explained beats broad
  and untested every time.
