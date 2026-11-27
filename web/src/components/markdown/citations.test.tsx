import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ReactMarkdown from 'react-markdown'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  CitationMarker,
  CitationProvider,
  citationNumber,
  remarkCitations,
} from '@/components/markdown/citations'

afterEach(cleanup)

function renderAnswer(content: string, available: number[], onActivate = vi.fn()) {
  render(
    <CitationProvider
      value={{ available: new Set(available), idFor: (n) => `src-${n}`, onActivate }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkCitations]}
        components={{
          a: ({ href, children }) => {
            const n = citationNumber(href)
            return n === null ? <a href={href}>{children}</a> : <CitationMarker n={n} />
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </CitationProvider>,
  )
  return onActivate
}

describe('citation markers', () => {
  it('link each cited number to its source', () => {
    const onActivate = renderAnswer('Leave is 25 days [1][2].', [1, 2])
    const first = screen.getByRole('link', { name: 'Source 1' })
    expect(first.getAttribute('href')).toBe('#src-1')
    expect(screen.getByRole('link', { name: 'Source 2' })).toBeTruthy()

    fireEvent.click(first)
    expect(onActivate).toHaveBeenCalledWith(1)
  })

  it('leave a number with no source behind it as the model wrote it', () => {
    renderAnswer('See [3].', [1])
    expect(screen.queryByRole('link')).toBeNull()
    expect(document.body.textContent).toBe('See [3].')
  })

  it('never touch code or real links', () => {
    renderAnswer('Use `arr[1]` and [docs](https://example.com/1).', [1])
    expect(screen.getByText('arr[1]')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'docs' }).getAttribute('href')).toBe(
      'https://example.com/1',
    )
    expect(screen.queryByRole('link', { name: 'Source 1' })).toBeNull()
  })
})
