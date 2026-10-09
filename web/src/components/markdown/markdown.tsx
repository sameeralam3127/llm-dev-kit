'use client'

import type { Element, Root, RootContent } from 'hast'
import { memo, useMemo } from 'react'
import ReactMarkdown, { type Components, type Options } from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { CodeBlock } from '@/components/markdown/code-block'
import { useHighlighter } from '@/hooks/use-highlighter'
import { hasCodeBlock, splitMarkdownBlocks } from '@/lib/markdown-blocks'
import { cn } from '@/lib/utils'

type RehypePlugins = NonNullable<Options['rehypePlugins']>

// Module-level so every block gets the same array identities; a fresh array
// per render would make react-markdown rebuild its processor each time.
const REMARK_PLUGINS: NonNullable<Options['remarkPlugins']> = [remarkGfm]
const NO_REHYPE_PLUGINS: RehypePlugins = []
const highlightPlugins = new WeakMap<object, RehypePlugins>()

/** Anything not on this list is dropped, which kills `javascript:` payloads. */
const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:'])

function sanitizeUrl(url: string): string {
  try {
    // Relative URLs resolve against the base and are always safe to keep.
    const parsed = new URL(url, 'https://example.invalid')
    return SAFE_PROTOCOLS.has(parsed.protocol) ? url : ''
  } catch {
    return ''
  }
}

/** Recursively collect the plain text of a hast node, for copy-to-clipboard. */
function textContent(node: Root | RootContent | undefined): string {
  if (!node) return ''
  if (node.type === 'text') return node.value
  if ('children' in node && Array.isArray(node.children)) {
    return node.children.map(textContent).join('')
  }
  return ''
}

function languageOf(node: Element | undefined): string | null {
  const className = node?.properties?.['className']
  const classes = Array.isArray(className) ? className.map(String) : []
  const match = classes.find((entry) => entry.startsWith('language-'))
  return match ? match.slice('language-'.length) : null
}

const components: Components = {
  // Fenced blocks get the chrome (language label, copy, soft-wrap toggle);
  // inline code is left to the stylesheet.
  pre({ node, children }) {
    const codeNode = (node?.children ?? []).find(
      (child: RootContent): child is Element =>
        child.type === 'element' && child.tagName === 'code',
    )

    return (
      <CodeBlock language={languageOf(codeNode)} code={textContent(codeNode)}>
        {children}
      </CodeBlock>
    )
  },

  a({ href, children, ...props }) {
    const safeHref = href ? sanitizeUrl(href) : ''
    if (!safeHref) return <span>{children}</span>

    const isExternal = /^https?:/i.test(safeHref)
    return (
      <a
        href={safeHref}
        {...(isExternal
          ? { target: '_blank', rel: 'noopener noreferrer nofollow' }
          : {})}
        {...props}
      >
        {children}
      </a>
    )
  },

  table({ children, ...props }) {
    // Wide tables scroll on their own rather than forcing the page sideways.
    return (
      <div className="scrollbar-thin my-4 w-full overflow-x-auto rounded-md border border-border">
        <table {...props}>{children}</table>
      </div>
    )
  },

  img({ src, alt, ...props }) {
    const safeSrc = typeof src === 'string' ? sanitizeUrl(src) : ''
    if (!safeSrc) return null
    // eslint-disable-next-line @next/next/no-img-element -- model output points at arbitrary hosts, which next/image cannot optimise
    return <img src={safeSrc} alt={alt ?? ''} loading="lazy" {...props} />
  },
}

interface MarkdownProps {
  content: string
  className?: string
  /**
   * The content is still arriving. Its last block may be incomplete (an open
   * code fence, half a table), so it is rendered without highlighting until
   * the next block starts or the stream ends.
   */
  streaming?: boolean
}

/**
 * Renders block by block (see `splitMarkdownBlocks`) so a streaming answer
 * re-parses only its growing last block per frame instead of the whole text.
 * Memoised on its props, so sibling messages are never re-parsed alongside it.
 */
export const Markdown = memo(function Markdown({
  content,
  className,
  streaming = false,
}: MarkdownProps) {
  const blocks = useMemo(() => splitMarkdownBlocks(content), [content])
  const highlight = useHighlighter(hasCodeBlock(content))
  const highlighted = highlight ? pluginsFor(highlight) : NO_REHYPE_PLUGINS

  return (
    <div className={cn('markdown-body', className)}>
      {blocks.map((block, index) => (
        <MarkdownBlock
          // Blocks only ever append; the index is a stable identity.
          // eslint-disable-next-line react/no-array-index-key
          key={index}
          content={block}
          rehypePlugins={
            streaming && index === blocks.length - 1 ? NO_REHYPE_PLUGINS : highlighted
          }
        />
      ))}
    </div>
  )
})

const MarkdownBlock = memo(function MarkdownBlock({
  content,
  rehypePlugins,
}: {
  content: string
  rehypePlugins: RehypePlugins
}) {
  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      rehypePlugins={rehypePlugins}
      urlTransform={sanitizeUrl}
      components={components}
    >
      {content}
    </ReactMarkdown>
  )
})

/** One stable plugin list per loaded highlighter, so memoised blocks stay memoised. */
function pluginsFor(plugin: RehypePlugins[number]): RehypePlugins {
  const key = plugin as object
  let list = highlightPlugins.get(key)
  if (!list) {
    list = [plugin]
    highlightPlugins.set(key, list)
  }
  return list
}
