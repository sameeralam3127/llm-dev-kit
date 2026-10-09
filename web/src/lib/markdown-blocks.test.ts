import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { describe, expect, it } from 'vitest'

import { hasCodeBlock, splitMarkdownBlocks } from '@/lib/markdown-blocks'

const render = (markdown: string) =>
  renderToStaticMarkup(createElement(ReactMarkdown, { remarkPlugins: [remarkGfm] }, markdown))

/**
 * Whitespace between top-level elements (or escaped tags) is not rendered;
 * compare without it. Whitespace inside text and code is left alone.
 */
const normalise = (html: string) => html.replace(/(>|&gt;)\s+(<|&lt;)/g, '$1$2').trim()

/** Answers shaped like real model output, including the awkward cases. */
const CORPUS = {
  paragraphs: 'First paragraph.\n\nSecond paragraph with **bold** and `code`.\n\n\nThird after two blanks.',
  headingsAndLists:
    '## Steps\n\n1. Install\n2. Configure\n3. Run\n\nThen check:\n\n- one\n- two\n\n### Notes\n\nDone.',
  looseList: '- first item\n\n- second item\n\n  continued paragraph in item two\n\n- third\n\nAfter the list.',
  orderedLooseList: '1. Alpha\n\n2. Beta\n\n3. Gamma',
  fenceWithBlankLines:
    'Here is code:\n\n```python\ndef f():\n\n    return 1\n\n\nprint(f())\n```\n\nAnd after it.',
  tildeFence: '~~~\nraw\n\n~~~ not a close\n~~~\n\nText.',
  longerFenceClose: '````md\n```js\ninner\n```\n````\n\nAfter.',
  indentedCode: 'Paragraph:\n\n    indented code\n\n    more code\n\nBack to text.',
  table: '| a | b |\n|---|---|\n| 1 | 2 |\n\nCaption paragraph.',
  blockquote: '> quoted line\n>\n> second line\n\n> separate quote\n\nPlain.',
  nestedList: '- outer\n  - inner\n\n    inner paragraph\n- outer two\n\nEnd.',
  thematicBreak: 'Above\n\n---\n\nBelow',
  html: '<div>\n\nnot raw\n\n</div>\n\nText.',
  trailingNewlines: 'Ends with blank lines.\n\n\n',
} satisfies Record<string, string>

describe('splitMarkdownBlocks', () => {
  it.each(Object.entries(CORPUS))('renders %s identically when split', (_, markdown) => {
    const blocks = splitMarkdownBlocks(markdown)
    expect(normalise(blocks.map(render).join(''))).toBe(normalise(render(markdown)))
  })

  it('splits at blank lines between independent blocks', () => {
    expect(splitMarkdownBlocks('# Title\n\nPara one.\n\nPara two.')).toEqual([
      '# Title',
      'Para one.',
      'Para two.',
    ])
  })

  it('never splits inside a code fence', () => {
    const fence = '```\na\n\nb\n```'
    expect(splitMarkdownBlocks(`Intro\n\n${fence}\n\nOutro`)).toEqual(['Intro', fence, 'Outro'])
  })

  it('keeps an unclosed fence (mid-stream) as one growing block', () => {
    expect(splitMarkdownBlocks('Text\n\n```js\nconst a = 1\n\nconst b')).toEqual([
      'Text',
      '```js\nconst a = 1\n\nconst b',
    ])
  })

  it('keeps list items that might form a loose list together', () => {
    expect(splitMarkdownBlocks('- a\n\n- b\n\n1. c')).toEqual(['- a\n\n- b\n\n1. c'])
  })

  it('does not split content that uses reference definitions or footnotes', () => {
    const withRef = 'See [docs][1].\n\nMore.\n\n[1]: https://example.com'
    const withFootnote = 'Claim.[^n]\n\nMore.\n\n[^n]: Source.'
    expect(splitMarkdownBlocks(withRef)).toEqual([withRef])
    expect(splitMarkdownBlocks(withFootnote)).toEqual([withFootnote])
  })

  it('earlier blocks stay byte-identical as a stream grows', () => {
    const full = CORPUS.headingsAndLists
    let previous: string[] = []
    for (let end = 1; end <= full.length; end++) {
      const blocks = splitMarkdownBlocks(full.slice(0, end))
      // Every block but the last two (the one just finished may lose its
      // trailing newline once the next block starts) is unchanged.
      expect(blocks.slice(0, -2)).toEqual(previous.slice(0, Math.max(0, blocks.length - 2)))
      previous = blocks
    }
  })

  it('handles empty input', () => {
    expect(splitMarkdownBlocks('')).toEqual([''])
  })
})

describe('hasCodeBlock', () => {
  it.each([
    ['```js\nx\n```', true],
    ['~~~\nx\n~~~', true],
    ['para\n\n    indented', true],
    ['no code, only `inline`', false],
  ])('%j -> %s', (markdown, expected) => {
    expect(hasCodeBlock(markdown)).toBe(expected)
  })
})
