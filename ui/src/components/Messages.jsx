import { useEffect, useRef } from "react";

import { FileText, Sparkles } from "../icons.jsx";
import { escapeHtml, renderMarkdown } from "../markdown.js";

const SUGGESTIONS = [
  "Summarize my knowledge base",
  "What did the last indexed document cover?",
  "Explain this project's architecture",
];

function Sources({ sources }) {
  if (!sources?.length) return null;
  return (
    <details className="sources">
      <summary>
        {sources.length} source{sources.length > 1 ? "s" : ""}
      </summary>
      {sources.map((s, i) => (
        <pre key={i}>{s}</pre>
      ))}
    </details>
  );
}

function Message({ msg }) {
  if (msg.role === "user") {
    return (
      <div className="msg user">
        <div className="bubble">{msg.content}</div>
      </div>
    );
  }
  if (msg.role === "system") {
    return (
      <div className="msg system">
        <span className="note">
          <FileText width={14} height={14} /> {msg.content}
        </span>
      </div>
    );
  }
  const html =
    renderMarkdown(msg.content) +
    (msg.streaming ? '<span class="cursor"></span>' : "") +
    (msg.error
      ? `<div class="msg-error">Error: ${escapeHtml(msg.error)}</div>`
      : "");
  return (
    <div className="msg bot">
      <div
        className="bubble"
        dangerouslySetInnerHTML={{
          __html: html || "<i>(empty response)</i>",
        }}
      />
      <div className="tags">
        {msg.cached && <span className="tag cache">⚡ cached</span>}
        {msg.model && !msg.streaming && <span className="tag">{msg.model}</span>}
      </div>
      <Sources sources={msg.sources} />
    </div>
  );
}

export default function Messages({ messages, onSuggest }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <div id="chat" ref={scrollRef}>
      <div className="inner">
        {messages.length === 0 && (
          <div className="empty">
            <div className="glyph">
              <Sparkles width={24} height={24} />
            </div>
            <h2>Ask anything</h2>
            <p>
              Answers are grounded in your indexed documents.
              <br />
              Attach a PDF with the 📎 in the message bar to grow the knowledge
              base.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => onSuggest(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <Message key={i} msg={m} />
        ))}
      </div>
    </div>
  );
}
