'use client'

import type { Link, Parent, PhrasingContent, Root, Text } from 'mdast'
import * as React from 'react'

/**
 * Grounded answers cite their passages as [1], [2][3]. This turns those
 * markers into links the renderer can recognise, and the context below decides
 * whether each one points at a real source: a marker with nothing behind it
 * (a non-grounded answer, a number out of range, a shared page) stays plain
 * text, exactly as the model wrote it.
 */
const MARKER = /\[(\d{1,2})\]/g
const CITE_PREFIX = '#cite-'

export function remarkCitations() {
  return (tree: Root) => {
    visit(tree)
  }
}

function visit(node: Parent): void {
  // Inside a link a marker is the link's own text, not a citation.
  if (node.type === 'link' || node.type === 'linkReference') return

  let changed = false
  const next: Parent['children'] = []
  for (const child of node.children) {
    if (child.type === 'text' && child.value.includes('[')) {
      const parts = splitMarkers(child)
      if (parts.length > 1 || parts[0] !== child) changed = true
      next.push(...parts)
    } else {
      if ('children' in child) visit(child)
      next.push(child)
    }
  }
  if (changed) node.children = next as typeof node.children
}

function splitMarkers(node: Text): PhrasingContent[] {
  const out: PhrasingContent[] = []
  let last = 0
  for (const match of node.value.matchAll(MARKER)) {
    const start = match.index ?? 0
    if (start > last) out.push({ type: 'text', value: node.value.slice(last, start) })
    const link: Link = {
      type: 'link',
      url: `${CITE_PREFIX}${match[1]}`,
      children: [{ type: 'text', value: match[1] ?? '' }],
    }
    out.push(link)
    last = start + match[0].length
  }
  if (out.length === 0) return [node]
  if (last < node.value.length) out.push({ type: 'text', value: node.value.slice(last) })
  return out
}

export function citationNumber(href: string | undefined): number | null {
  if (!href?.startsWith(CITE_PREFIX)) return null
  const n = Number(href.slice(CITE_PREFIX.length))
  return Number.isInteger(n) && n > 0 ? n : null
}

interface CitationContextValue {
  /** The numbers that have a source behind them. */
  available: ReadonlySet<number>
  /** Element id for source `n`, so a marker is a real in-page link. */
  idFor: (n: number) => string
  onActivate: (n: number) => void
}

const CitationContext = React.createContext<CitationContextValue | null>(null)

export const CitationProvider = CitationContext.Provider

export function CitationMarker({ n }: { n: number }) {
  const context = React.useContext(CitationContext)
  if (!context?.available.has(n)) return <>[{n}]</>

  return (
    <a
      href={`#${context.idFor(n)}`}
      className="citation-ref"
      aria-label={`Source ${n}`}
      onClick={(event) => {
        event.preventDefault()
        context.onActivate(n)
      }}
    >
      {n}
    </a>
  )
}
