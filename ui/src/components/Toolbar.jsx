import { Refresh } from "../icons.jsx";

const PROVIDERS = [
  { id: "ollama", label: "Local (Ollama)" },
  { id: "openai", label: "OpenAI" },
  { id: "gemini", label: "Gemini" },
  { id: "anthropic", label: "Anthropic" },
];

export default function Toolbar({
  provider,
  setProvider,
  model,
  setModel,
  models,
  modelsLoading,
  modelsError,
  reloadModels,
  apiKey,
  setApiKey,
}) {
  const providerModels = models.filter((m) =>
    provider === "ollama" ? !m.includes("/") : m.startsWith(provider + "/")
  );

  return (
    <div className="toolbar">
      <label>Provider</label>
      <select value={provider} onChange={(e) => setProvider(e.target.value)}>
        {PROVIDERS.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label}
          </option>
        ))}
      </select>

      <label>Model</label>
      <select value={model} onChange={(e) => setModel(e.target.value)}>
        {providerModels.map((m) => (
          <option key={m} value={m}>
            {provider === "ollama" ? m : m.slice(provider.length + 1)}
          </option>
        ))}
        {!providerModels.length && (
          <option value="">
            {modelsLoading
              ? "loading models…"
              : modelsError
                ? "backend unreachable"
                : provider === "ollama"
                  ? "no local models found"
                  : "no models"}
          </option>
        )}
      </select>
      <button
        className="icon-btn"
        onClick={reloadModels}
        title="Refresh model list"
        disabled={modelsLoading}
      >
        <Refresh width={15} height={15} />
      </button>
      {modelsError && <span className="error-note">{modelsError}</span>}

      {provider !== "ollama" && (
        <span className="api-key">
          <label htmlFor="apiKey">API key</label>
          <input
            id="apiKey"
            type="password"
            placeholder="paste key (stored locally)"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value.trim())}
          />
        </span>
      )}
    </div>
  );
}
