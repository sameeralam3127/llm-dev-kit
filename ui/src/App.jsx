import { useCallback, useEffect, useState } from "react";

import { clearCache, streamChat } from "./api.js";
import Composer from "./components/Composer.jsx";
import Header from "./components/Header.jsx";
import Messages from "./components/Messages.jsx";
import Toolbar from "./components/Toolbar.jsx";
import { useModels, useStatus, useStoredState, useTheme } from "./hooks.js";

export default function App() {
  const { models, loading: modelsLoading, error: modelsError, reload } =
    useModels();
  const { status, refresh: refreshStatus } = useStatus();
  const [theme, toggleTheme] = useTheme();

  const [provider, setProvider] = useStoredState("llmdevkit-provider", "ollama");
  const [model, setModel] = useStoredState("llmdevkit-model-" + provider);
  const [apiKey, setApiKey] = useStoredState("llmdevkit-key-" + provider);

  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [toast, setToast] = useState(null);

  const notify = useCallback((text, isError = false) => {
    setToast({ text, isError });
    setTimeout(() => setToast(null), 3500);
  }, []);

  // Keep the selected model valid for the current provider.
  const providerModels = models.filter((m) =>
    provider === "ollama" ? !m.includes("/") : m.startsWith(provider + "/")
  );
  useEffect(() => {
    if (providerModels.length && !providerModels.includes(model)) {
      setModel(providerModels[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, models]);

  const patchLast = (patch) =>
    setMessages((prev) => {
      const next = prev.slice();
      next[next.length - 1] = { ...next[next.length - 1], ...patch };
      return next;
    });

  async function send(text) {
    if (!model) {
      notify("Pick a model first — is the backend up?", true);
      return;
    }
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "bot", content: "", streaming: true, sources: [] },
    ]);
    setStreaming(true);
    try {
      await streamChat(
        { message: text, model, apiKey: provider === "ollama" ? null : apiKey },
        {
          onMeta: (meta) =>
            patchLast({ cached: meta.cached, sources: meta.sources || [] }),
          onDelta: (delta) =>
            setMessages((prev) => {
              const next = prev.slice();
              const last = next[next.length - 1];
              next[next.length - 1] = {
                ...last,
                content: last.content + delta,
              };
              return next;
            }),
          onDone: (done) => patchLast({ model: done.model }),
        }
      );
    } catch (err) {
      patchLast({ error: String(err.message || err) });
    } finally {
      patchLast({ streaming: false });
      setStreaming(false);
      refreshStatus();
    }
  }

  function handleIndexed(name, chunks) {
    setMessages((prev) => [
      ...prev,
      {
        role: "system",
        content: `${name} indexed — ${chunks} chunk${chunks === 1 ? "" : "s"} added to the knowledge base`,
      },
    ]);
    refreshStatus();
  }

  return (
    <>
      <Header
        status={status}
        theme={theme}
        onToggleTheme={toggleTheme}
        onClearCache={async () => {
          try {
            const res = await clearCache();
            notify(`Cleared ${res.cleared} cached responses`);
            refreshStatus();
          } catch {
            notify("Cache clear failed", true);
          }
        }}
        onNewChat={() => setMessages([])}
      />
      <Toolbar
        provider={provider}
        setProvider={setProvider}
        model={model}
        setModel={setModel}
        models={models}
        modelsLoading={modelsLoading}
        modelsError={modelsError}
        reloadModels={reload}
        apiKey={apiKey}
        setApiKey={setApiKey}
      />
      <Messages messages={messages} onSuggest={send} />
      <Composer
        onSend={send}
        onIndexed={handleIndexed}
        notify={notify}
        disabled={streaming}
      />
      {toast && (
        <div id="toast" className={toast.isError ? "err" : undefined}>
          {toast.text}
        </div>
      )}
    </>
  );
}
