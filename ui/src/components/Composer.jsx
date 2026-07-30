import { useEffect, useRef, useState } from "react";

import { ingestPdf } from "../api.js";
import { FileText, Paperclip, Send, X } from "../icons.jsx";

export default function Composer({ onSend, onIndexed, notify, disabled }) {
  const inputRef = useRef(null);
  const fileRef = useRef(null);
  // {name, status: "indexing" | "error", detail}
  const [attachment, setAttachment] = useState(null);
  const [dragging, setDragging] = useState(false);

  // Whole-window drag & drop for PDFs.
  useEffect(() => {
    let depth = 0;
    const enter = (e) => {
      if (!e.dataTransfer?.types?.includes("Files")) return;
      e.preventDefault();
      depth++;
      setDragging(true);
    };
    const over = (e) => e.preventDefault();
    const leave = () => {
      if (--depth <= 0) {
        depth = 0;
        setDragging(false);
      }
    };
    const drop = (e) => {
      e.preventDefault();
      depth = 0;
      setDragging(false);
      indexFile(e.dataTransfer.files?.[0]);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function submit() {
    const text = inputRef.current.value.trim();
    if (!text || disabled) return;
    inputRef.current.value = "";
    inputRef.current.style.height = "auto";
    onSend(text);
  }

  function autoSize() {
    const el = inputRef.current;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 170) + "px";
  }

  async function indexFile(file) {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.endsWith(".pdf")) {
      notify("Only PDF files can be attached", true);
      return;
    }
    setAttachment({ name: file.name, status: "indexing" });
    try {
      const res = await ingestPdf(file);
      setAttachment(null);
      onIndexed(file.name, res.chunks);
    } catch (err) {
      setAttachment({
        name: file.name,
        status: "error",
        detail: String(err.message || err),
      });
    }
  }

  function handlePick(e) {
    const file = e.target.files[0];
    e.target.value = "";
    indexFile(file);
  }

  return (
    <footer>
      {dragging && (
        <div className="drop-overlay">
          <div className="card">
            <FileText /> Drop a PDF to index it
          </div>
        </div>
      )}
      <div className="composer-wrap">
        {attachment && (
          <div
            className={
              "attachment-chip" + (attachment.status === "error" ? " err" : "")
            }
          >
            {attachment.status === "indexing" ? (
              <span className="spin" />
            ) : (
              <FileText width={15} height={15} />
            )}
            <span className="name">{attachment.name}</span>
            <span>
              {attachment.status === "indexing"
                ? "indexing…"
                : attachment.detail}
            </span>
            <button
              className="icon-btn"
              onClick={() => setAttachment(null)}
              title="Dismiss"
            >
              <X width={13} height={13} />
            </button>
          </div>
        )}

        <div className="composer">
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            hidden
            onChange={handlePick}
          />
          <button
            className="icon-btn"
            onClick={() => fileRef.current.click()}
            disabled={attachment?.status === "indexing"}
            title="Attach a PDF — it gets indexed into the knowledge base"
          >
            <Paperclip />
          </button>
          <textarea
            ref={inputRef}
            rows={1}
            placeholder="Message… (attach a PDF with the clip)"
            autoFocus
            onInput={autoSize}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <button
            className="send-btn"
            onClick={submit}
            disabled={disabled}
            title="Send (Enter)"
          >
            <Send width={17} height={17} />
          </button>
        </div>
        <div className="hint">
          Enter to send · Shift+Enter for a new line · drop a PDF anywhere to
          index it
        </div>
      </div>
    </footer>
  );
}
