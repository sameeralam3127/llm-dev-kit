'use client'

import type { Element, Root, RootContent } from 'hast'
import { memo } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'

import { CodeBlock } from '@/components/markdown/code-block'
import { cn } from '@/lib/utils'

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
}

/**
 * Memoised on `content`: a streaming answer re-renders roughly once per frame,
 * and without this every sibling message would be re-parsed alongside it.
 */
export const Markdown = memo(function Markdown({ content, className }: MarkdownProps) {
  return (
    <div className={cn('markdown-body', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        // `ignoreMissing` keeps an unknown fence language from throwing
        // mid-stream, which would blank the whole message.
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        urlTransform={sanitizeUrl}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
})
