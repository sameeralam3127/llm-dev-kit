'use client'

import { ChevronRight } from 'lucide-react'
import * as React from 'react'

import { cn } from '@/lib/utils'
import type { MessageSource } from '@/types/chat'

interface MessageSourcesProps {
  sources: MessageSource[]
  /** Prefix for each row's id; inline [n] markers link to `${idPrefix}-n`. */
  idPrefix: string
  open: boolean
  onOpenChange: (open: boolean) => void
  /** The row a marker just pointed at; highlighted briefly. */
  active: number | null
}

/**
 * The passages an answer was built from, set like a report's footnotes: a
 * numbered list under a hairline rule, each entry naming its document and
 * quoting the passage. Closed by default so the answer reads first; an inline
 * marker opens it at the right row.
 */
export function MessageSources({
  sources,
  idPrefix,
  open,
  onOpenChange,
  active,
}: MessageSourcesProps) {
  const listId = `${idPrefix}-list`
  const documents = new Set(sources.map((source) => source.title).filter(Boolean)).size

  return (
    <section className="mt-4" aria-label="Sources">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => onOpenChange(!open)}
        className="group/sources inline-flex items-center gap-1.5 rounded-md py-1 pr-2 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronRight
          className={cn('size-3.5 transition-transform motion-reduce:transition-none', open && 'rotate-90')}
          aria-hidden="true"
        />
        {summary(sources.length, documents)}
      </button>

      {open && (
        <ol id={listId} className="mt-2 border-l border-border pl-4">
          {sources.map((source) => (
            <SourceRow
              key={source.index}
              source={source}
              id={`${idPrefix}-${source.index}`}
              highlighted={active === source.index}
            />
          ))}
        </ol>
      )}
    </section>
  )
}

function summary(passages: number, documents: number): string {
  const p = `${passages} ${passages === 1 ? 'passage' : 'passages'}`
  if (documents > 1) return `Answered from ${p} in ${documents} documents`
  return `Answered from ${p}`
}

function SourceRow({
  source,
  id,
  highlighted,
}: {
  source: MessageSource
  id: string
  highlighted: boolean
}) {
  const [expanded, setExpanded] = React.useState(false)
  const ref = React.useRef<HTMLLIElement>(null)

  // Arriving from a marker: bring the row into view and give it focus, so
  // keyboard and screen-reader users land where sighted users look.
  React.useEffect(() => {
    if (!highlighted) return
    const row = ref.current
    if (!row) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    row.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
    row.focus({ preventScroll: true })
  }, [highlighted])

  const long = source.snippet.length > 220

  return (
    <li
      ref={ref}
      id={id}
      tabIndex={-1}
      data-active={highlighted || undefined}
      className="source-row relative -ml-4 grid grid-cols-[2rem_1fr] gap-x-1 py-2.5 pl-4 pr-2 outline-none"
    >
      <span className="pt-px text-xs font-semibold tabular-nums text-primary">{source.index}</span>

      <div className="min-w-0">
        {source.title && (
          <p className="flex min-w-0 items-baseline gap-2 text-[0.8125rem] font-medium leading-5">
            <span className="truncate">{source.title}</span>
            {source.page !== null && (
              <span className="shrink-0 text-xs font-normal text-muted-foreground">
                page {source.page}
              </span>
            )}
          </p>
        )}

        <blockquote
          className={cn(
            'text-[0.8125rem] leading-6 text-muted-foreground',
            source.title && 'mt-0.5',
            !expanded && long && 'line-clamp-2',
          )}
        >
          {source.snippet}
        </blockquote>

        {long && (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="mt-0.5 rounded text-xs font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {expanded ? 'Show less' : 'Show full passage'}
          </button>
        )}
      </div>
    </li>
  )
}
