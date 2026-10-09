/**
 * Cost of rendering one streamed answer, frame by frame: `npm run bench`.
 * Runs only in bench mode (see vitest.config.mts); reports median times.
 *
 * "whole document" is how Markdown rendered before blocks: the entire text is
 * parsed and highlighted (with language auto-detection) on every frame.
 */
import { act, render } from '@testing-library/react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'
import { beforeAll, describe, expect, it } from 'vitest'

import { Markdown } from '@/components/markdown/markdown'
import { loadHighlighter } from '@/hooks/use-highlighter'

const SECTION = `## Setting up the service

Local-first software keeps the primary copy of data on the user's machine.
Sync is an optimisation, not a dependency, so the app keeps working offline.

1. Install the dependencies
2. Configure the environment
3. Start the stack and open the gateway

\`\`\`python
def chunk(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size].strip())
        start += size - overlap
    return [c for c in chunks if c]
\`\`\`

| Setting | Default | Notes |
| --- | --- | --- |
| \`CHUNK_SIZE\` | 500 | characters |
| \`OVERLAP\` | 50 | shared between windows |

\`\`\`bash
docker compose up -d
curl -s localhost:8080/api/rag/health
\`\`\`

`

const ANSWER = SECTION.repeat(4)
const CHARS_PER_FRAME = 40
const FRAMES = Array.from(
  { length: Math.ceil(ANSWER.length / CHARS_PER_FRAME) },
  (_, i) => ANSWER.slice(0, (i + 1) * CHARS_PER_FRAME),
)

function WholeDocument({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true }]]}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

beforeAll(async () => {
  // Measure steady state: the highlighter chunk is already loaded.
  await loadHighlighter()
})

const RUNS = 7

function median(run: () => void): number {
  run() // warm-up: JIT and module caches
  const times = Array.from({ length: RUNS }, () => {
    const t0 = performance.now()
    run()
    return performance.now() - t0
  }).sort((a, b) => a - b)
  return times[Math.floor(RUNS / 2)] ?? Number.NaN
}

describe('streaming render cost', () => {
  it(`streams a ${ANSWER.length}-character answer in ${FRAMES.length} frames`, async ({
    annotate,
  }) => {
    const before = median(() => {
      const { rerender, unmount } = render(<WholeDocument content="" />)
      for (const frame of FRAMES) act(() => rerender(<WholeDocument content={frame} />))
      unmount()
    })
    const after = median(() => {
      const { rerender, unmount } = render(<Markdown content="" streaming />)
      for (const frame of FRAMES) act(() => rerender(<Markdown content={frame} streaming />))
      act(() => rerender(<Markdown content={ANSWER} />))
      unmount()
    })

    // Reported as test annotations, so the numbers appear in the run output.
    await annotate(
      [
        `whole document per frame (before): ${before.toFixed(0)} ms`,
        `block-memoised Markdown   (after): ${after.toFixed(0)} ms`,
        `speed-up: ${(before / after).toFixed(1)}x`,
      ].join('\n'),
    )
    expect(after).toBeLessThan(before)
  }, 120_000)
})
