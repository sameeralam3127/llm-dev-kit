import type * as React from 'react'

import { cn } from '@/lib/utils'

interface PageHeaderProps {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
}

/** The title block every admin page starts with. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}

/** A bordered panel with an optional heading row, for grouping a page's content. */
export function Panel({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: string
  description?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  const id = title ? `panel-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}` : undefined
  return (
    <section aria-labelledby={id} className={cn('rounded-lg border bg-card', className)}>
      {title && (
        <div className="flex items-start justify-between gap-4 border-b px-4 py-3">
          <div className="min-w-0">
            <h2 id={id} className="text-sm font-semibold">
              {title}
            </h2>
            {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}
