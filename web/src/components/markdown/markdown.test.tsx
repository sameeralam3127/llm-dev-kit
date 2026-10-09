import { act, render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { parses, highlighterLoaded, HIGHLIGHT } = vi.hoisted(() => ({
  /** One entry per react-markdown render, i.e. per block parse. */
  parses: [] as Array<{ content: string; highlighted: boolean }>,
  highlighterLoaded: { count: 0 },
  HIGHLIGHT: [() => undefined, {}] as const,
}))

vi.mock('react-markdown', () => ({
  default: (props: { children: string; rehypePlugins: unknown[] }) => {
    parses.push({ content: props.children, highlighted: props.rehypePlugins.length > 0 })
    return <p>{props.children}</p>
  },
}))

// The real module pulls in highlight.js; this stands in and records the load.
vi.mock('@/components/markdown/highlight', () => {
  highlighterLoaded.count += 1
  return { rehypeHighlightPlugin: HIGHLIGHT }
})

import { Markdown } from '@/components/markdown/markdown'

beforeEach(() => {
  parses.length = 0
})

describe('Markdown', () => {
  // Order matters: the highlighter chunk is cached for the module's lifetime,
  // so the "no code" case must run before anything loads it.
  it('re-parses only the growing block while streaming, and loads no highlighter', () => {
    const { rerender } = render(<Markdown content={'One.\n\nTwo'} streaming />)
    expect(parses.map((p) => p.content)).toEqual(['One.', 'Two'])

    parses.length = 0
    rerender(<Markdown content={'One.\n\nTwo grows'} streaming />)
    rerender(<Markdown content={'One.\n\nTwo grows more'} streaming />)
    expect(parses.map((p) => p.content)).toEqual(['Two grows', 'Two grows more'])

    parses.length = 0
    rerender(<Markdown content={'One.\n\nTwo grows more\n\nThree'} streaming />)
    expect(parses.map((p) => p.content)).toEqual(['Three'])

    expect(highlighterLoaded.count).toBe(0)
  })

  it('does not re-parse at all when the content is unchanged', () => {
    const { rerender } = render(<Markdown content={'Same.\n\nText.'} />)
    parses.length = 0
    rerender(<Markdown content={'Same.\n\nText.'} />)
    expect(parses).toEqual([])
  })

  it('loads the highlighter for code, and never highlights the live block', async () => {
    const streamingContent = 'Intro\n\n```js\nconst a = 1'
    const { rerender } = render(<Markdown content={streamingContent} streaming />)

    await waitFor(() => expect(highlighterLoaded.count).toBe(1))
    // Once loaded, only the finished block is re-parsed (now highlighted); the
    // live code block keeps its unhighlighted parse and is not touched.
    await waitFor(() => expect(parses.at(-1)).toEqual({ content: 'Intro', highlighted: true }))
    expect(parses.filter((p) => p.content.startsWith('```'))).toEqual([
      { content: '```js\nconst a = 1', highlighted: false },
    ])

    parses.length = 0
    await act(async () => {
      rerender(<Markdown content={`${streamingContent}\n\`\`\``} streaming={false} />)
    })
    // Finished: the code block is highlighted; the intro is not parsed again.
    expect(parses).toEqual([{ content: '```js\nconst a = 1\n```', highlighted: true }])
    expect(highlighterLoaded.count).toBe(1)
  })
})
