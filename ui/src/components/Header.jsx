import { Moon, Plus, Sparkles, Sun, Trash } from "../icons.jsx";

function Dot({ ok }) {
  const cls = ok === null ? "dot" : ok ? "dot ok" : "dot bad";
  return <span className={cls} />;
}

export default function Header({
  status,
  theme,
  onToggleTheme,
  onClearCache,
  onNewChat,
}) {
  return (
    <header>
      <div className="brand">
        <div className="brand-mark">
          <Sparkles width={17} height={17} />
        </div>
        <h1>
          LLM <span>Dev Kit</span>
        </h1>
      </div>

      <span className="pill" title="llm-service health">
        <Dot ok={status.llm} /> LLM
      </span>
      <span className="pill" title="Indexed PDF chunks">
        <Dot ok={status.docs} /> Docs <b>{status.docCount}</b>
      </span>
      <span className="pill" title="Cached responses in Redis">
        <Dot ok={status.cache} /> Cache <b>{status.cacheKeys}</b>
      </span>

      <button
        className="icon-btn"
        onClick={onClearCache}
        title="Clear the Redis response cache"
      >
        <Trash />
      </button>
      <button
        className="icon-btn"
        onClick={onToggleTheme}
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        {theme === "dark" ? <Sun /> : <Moon />}
      </button>
      <button onClick={onNewChat} title="Start a new conversation">
        <Plus width={15} height={15} /> New chat
      </button>
    </header>
  );
}
