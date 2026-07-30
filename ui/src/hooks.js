import { useCallback, useEffect, useRef, useState } from "react";

import * as api from "./api.js";

const RETRY_MS = 3000;
const MAX_RETRIES = 20;

// Model list with automatic retry — right after `docker compose up` the
// gateway can be up before llm-service is healthy, and a single failed
// fetch must not leave the picker empty forever.
export function useModels() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const attempt = useRef(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getModels();
      setModels(res.models || []);
      attempt.current = 0;
    } catch (err) {
      setError(String(err.message || err));
      if (attempt.current++ < MAX_RETRIES) setTimeout(load, RETRY_MS);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { models, loading, error, reload: load };
}

export function useStatus(pollMs = 30000) {
  const [status, setStatus] = useState({
    llm: null,
    docs: null,
    docCount: "–",
    cache: null,
    cacheKeys: "–",
  });

  const refresh = useCallback(async () => {
    const next = {};
    try {
      const h = await api.getLlmHealth();
      next.llm = h.status === "ok";
    } catch {
      next.llm = false;
    }
    try {
      const d = await api.getDocStats();
      next.docs = d.status === "connected";
      next.docCount = d.document_count;
    } catch {
      next.docs = false;
      next.docCount = "–";
    }
    try {
      const c = await api.getCacheStats();
      next.cache = c.status === "connected";
      next.cacheKeys = c.keys;
    } catch {
      next.cache = false;
      next.cacheKeys = "–";
    }
    setStatus((prev) => ({ ...prev, ...next }));
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  return { status, refresh };
}

// Dark/light theme: follows the OS preference until the user toggles, then
// the choice is remembered. The theme is applied as data-theme on <html>.
export function useTheme() {
  const [theme, setTheme] = useState(
    () =>
      localStorage.getItem("llmdevkit-theme") ||
      (window.matchMedia?.("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark")
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("llmdevkit-theme", theme);
  }, [theme]);
  const toggle = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    []
  );
  return [theme, toggle];
}

// localStorage-backed state (API keys, remembered model per provider).
export function useStoredState(key, initial = "") {
  const [value, setValue] = useState(
    () => localStorage.getItem(key) ?? initial
  );
  useEffect(() => {
    setValue(localStorage.getItem(key) ?? initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const set = useCallback(
    (v) => {
      setValue(v);
      localStorage.setItem(key, v);
    },
    [key]
  );
  return [value, set];
}
