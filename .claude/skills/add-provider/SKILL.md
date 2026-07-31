---
name: add-provider
description: "Add a new LLM provider (OpenAI, Anthropic, Gemini, Groq, OpenRouter, LM Studio, Azure…) to the web app behind the ChatProvider interface. Use when the user wants to connect a new model host, add provider switching, or work on Phase 2 of the roadmap."
---

# Add an LLM provider

Every token-generating backend sits behind `ChatProvider`
(`web/src/lib/llm/types.ts`):

```ts
interface ChatProvider {
  readonly name: string
  listModels(signal?: AbortSignal): Promise<ProviderModel[]>
  streamCompletion(request: CompletionRequest): AsyncIterable<string>
}
```

The app (routes, hooks, UI) never sees anything else. Adding a provider is
one adapter + registry wiring — no route or component changes.

## Decision first: does it need a new adapter at all?

Many hosts are OpenAI-compatible. **Groq, OpenRouter, LM Studio, Ollama,
Azure OpenAI, Together, Fireworks** all speak `/v1/chat/completions` — for
these, reuse `OpenAICompatibleProvider` (`web/src/lib/llm/openai-compatible.ts`)
with a different `baseUrl`/`apiKey`, and only write a subclass if the host
deviates (Azure's `api-version` query param and `api-key` header, for
example). Write a full adapter only for genuinely different wire formats:
Anthropic's `/v1/messages` event types, Gemini's `streamGenerateContent`.

## Steps

1. **Read the existing pattern**: `openai-compatible.ts` end to end. Note how
   it distinguishes caller-abort vs upstream-down vs timeout — every adapter
   must keep those semantics, the UI depends on the `ProviderError` codes.
2. **Create the adapter** in `web/src/lib/llm/<provider>.ts`:
   - Parse the host's streaming format with `parseSSE` (`lib/llm/sse.ts`) if
     it is SSE; write a minimal incremental parser if not. Never buffer the
     whole response.
   - Map failures to `ProviderError` with the right code
     (`rate_limited` on 429, `timeout`, `upstream_unavailable` on
     connect-failure, `upstream_error` otherwise).
   - Yield plain text deltas; nothing else crosses the seam.
3. **Config**: add the provider's env vars to `web/src/lib/env.ts` (optional —
   the provider registers only when its key is present), and document them in
   `web/.env.example` and `sample.env`.
4. **Registry**: extend `getChatProvider()` (`web/src/lib/llm/index.ts`) into
   a keyed registry that routes `provider/model` ids — `anthropic/claude-…` →
   Anthropic adapter, bare ids → default provider. Keep `getAvailableModels()`
   merging all registered providers' lists, each entry labelled with its
   provider for the grouped model picker.
5. **Verify** — non-negotiable:
   - `npm run typecheck && npm run build` in `web/`
   - `/smoke-test` if the stack is running, or at minimum a curl streaming
     turn against the new provider with a real or mock key
   - Kill the provider mid-stream once and confirm the partial answer is
     persisted with `truncated=true` and the error surfaced in the UI shape.

## Sampling parameters (temperature, top-p, max tokens, penalties)

Add them to `CompletionRequest` as optional fields; adapters translate to
their host's naming (`max_tokens` vs `maxOutputTokens`) and **omit anything
the host does not support** rather than erroring. UI wiring is a separate
increment — do not block a provider on it.

## Learning note to leave behind

After each provider, record in `docs/ROADMAP.md` (Phase 2 section): what was
genuinely different about this host's API, and what the adapter had to absorb
so the rest of the app didn't notice. That accumulated list *is* the lesson
of Phase 2.
