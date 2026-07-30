// Minimal, fast markdown rendering: fenced code blocks, inline code, bold.
// Input is HTML-escaped first, so the produced HTML is safe to inject.

export function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function renderMarkdown(s) {
  let html = escapeHtml(s);
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    (_, _lang, code) => `<pre><code>${code}</code></pre>`
  );
  html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>");
  return html;
}
