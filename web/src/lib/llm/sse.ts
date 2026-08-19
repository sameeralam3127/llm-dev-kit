/**
 * Incremental parser for `text/event-stream`.
 *
 * Network chunks split anywhere — mid-field, mid-UTF-8-codepoint, mid-event —
 * so the decoder is streaming and the buffer only yields on a completed
 * blank-line-delimited event.
 */
export async function* parseSSE(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<{ event: string; data: string }> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Normalise CRLF so a single split pattern is enough.
      buffer = buffer.replace(/\r\n/g, '\n')

      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)

        const parsed = parseEvent(raw)
        if (parsed) yield parsed

        boundary = buffer.indexOf('\n\n')
      }
    }

    // A final event may arrive without its trailing blank line.
    const tail = parseEvent(buffer.trim())
    if (tail) yield tail
  } finally {
    reader.cancel().catch(() => {
      /* the consumer stopped caring; nothing to recover */
    })
    reader.releaseLock()
  }
}

function parseEvent(raw: string): { event: string; data: string } | null {
  if (!raw) return null

  let event = 'message'
  const dataLines: string[] = []

  for (const line of raw.split('\n')) {
    if (!line || line.startsWith(':')) continue

    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    // Spec: exactly one optional leading space after the colon is stripped.
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)

    if (field === 'event') event = value
    else if (field === 'data') dataLines.push(value)
  }

  if (dataLines.length === 0) return null
  return { event, data: dataLines.join('\n') }
}
