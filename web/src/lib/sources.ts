import type { MessageSource } from '@/types/chat'

/** Enough of a passage to recognise it; the full chunk stays in the index. */
const MAX_SNIPPET_CHARS = 600
const MAX_SOURCES = 20

/**
 * Narrows untrusted citation data (a backend stream chunk, or a stored JSON
 * column) to MessageSource[]. Malformed entries are dropped rather than
 * failing the answer they arrived with.
 */
export function parseSources(value: unknown): MessageSource[] {
  if (!Array.isArray(value)) return []

  const sources: MessageSource[] = []
  for (const [position, entry] of value.entries()) {
    if (!entry || typeof entry !== 'object') continue
    const raw = entry as Record<string, unknown>

    const snippet = typeof raw['snippet'] === 'string' ? raw['snippet'].trim() : ''
    if (!snippet) continue

    const index =
      typeof raw['index'] === 'number' && Number.isInteger(raw['index']) && raw['index'] > 0
        ? raw['index']
        : position + 1
    const title =
      typeof raw['title'] === 'string' && raw['title'].trim() ? raw['title'].trim() : null
    const page =
      typeof raw['page'] === 'number' && Number.isInteger(raw['page']) && raw['page'] > 0
        ? raw['page']
        : null

    sources.push({ index, title, page, snippet: snippet.slice(0, MAX_SNIPPET_CHARS) })
    if (sources.length === MAX_SOURCES) break
  }
  return sources
}

/** Reads the stored `Message.sources` column. */
export function parseStoredSources(value: string | null): MessageSource[] {
  if (!value) return []
  try {
    return parseSources(JSON.parse(value))
  } catch {
    return []
  }
}
