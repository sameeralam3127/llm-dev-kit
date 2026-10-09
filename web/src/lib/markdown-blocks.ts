/**
 * Split Markdown into top-level blocks that render identically on their own.
 *
 * A streaming answer re-renders about once per animation frame. Rendering it
 * as one document re-parses everything received so far on every frame, which
 * is quadratic over the answer's lifetime. Rendered block by block, only the
 * last (still growing) block changes, and memoised earlier blocks are skipped.
 *
 * Splitting is deliberately conservative: a cut is made only at a blank line
 * outside a code fence, and never where the next line could continue the
 * previous block (an indented line, or a list item that may belong to a loose
 * list). Content with reference definitions or footnotes is never split,
 * because a definition must sit in the same document as its references.
 */

const FENCE_OPEN = /^ {0,3}(`{3,}|~{3,})/
const CONTINUES_BLOCK = /^(?:[ \t]|[-*+][ \t]|\d{1,9}[.)][ \t])/
const DEFINITION = /^ {0,3}\[[^\]\n]+\]:/m

export function splitMarkdownBlocks(content: string): string[] {
  if (DEFINITION.test(content)) return [content]

  const lines = content.split('\n')
  const blocks: string[] = []
  let current: string[] = []
  let fence: string | null = null

  for (let index = 0; index < lines.length; index++) {
    const line = lines[index] ?? ''

    if (fence !== null) {
      current.push(line)
      if (closesFence(line, fence)) fence = null
      continue
    }

    const opening = FENCE_OPEN.exec(line)
    if (opening?.[1]) {
      fence = opening[1]
      current.push(line)
      continue
    }

    if (line.trim() === '' && current.length > 0) {
      let next = index + 1
      while (next < lines.length && (lines[next] ?? '').trim() === '') next++
      const following = lines[next]

      if (following !== undefined && !CONTINUES_BLOCK.test(following)) {
        blocks.push(current.join('\n'))
        current = []
        index = next - 1
        continue
      }
    }

    current.push(line)
  }

  if (current.length > 0) blocks.push(current.join('\n'))
  return blocks
}

/** A closing fence: same character, at least as long, nothing else on the line. */
function closesFence(line: string, fence: string): boolean {
  const trimmed = line.trim()
  if (trimmed.length < fence.length || /^ {4}/.test(line)) return false
  const char = fence.charAt(0)
  return [...trimmed].every((c) => c === char)
}

/** Whether the content contains anything the highlighter would colour. */
export function hasCodeBlock(content: string): boolean {
  return /^(?: {0,3}(?:`{3,}|~{3,})| {4}|\t)/m.test(content)
}
