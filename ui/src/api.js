// Thin API layer over the nginx gateway. All endpoints are same-origin
// (proxied by the vite dev server during development).

export async function fetchJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* not json */
    }
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const getModels = () => fetchJson("/api/llm/models");
export const getLlmHealth = () => fetchJson("/api/llm/health");
export const getDocStats = () => fetchJson("/api/rag/documents/stats");
export const getCacheStats = () => fetchJson("/api/rag/cache/stats");
export const clearCache = () =>
  fetchJson("/api/rag/cache/clear", { method: "POST" });

export async function ingestPdf(file) {
  const form = new FormData();
  form.append("file", file);
  return fetchJson("/api/rag/ingest/pdf", { method: "POST", body: form });
}

// Stream a RAG chat answer. Calls the handlers as NDJSON events arrive:
// onMeta({cached, sources}), onDelta(text), onDone({model}).
export async function streamChat({ message, model, apiKey }, handlers) {
  const res = await fetch("/api/rag/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, model, api_key: apiKey || null }),
  });
  if (!res.ok) throw new Error((await res.text()).slice(0, 300));

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      const evt = JSON.parse(line);
      if (evt.error) throw new Error(evt.error);
      if (evt.meta) handlers.onMeta?.(evt.meta);
      if (evt.delta) handlers.onDelta?.(evt.delta);
      if (evt.done) handlers.onDone?.(evt);
    }
  }
}
