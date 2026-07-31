'use client'

import { Check, Copy, WrapText } from 'lucide-react'
import * as React from 'react'

import { Button } from '@/components/ui/button'
import { useCopy } from '@/hooks/use-copy'
import { cn } from '@/lib/utils'

interface CodeBlockProps {
  language: string | null
  /** Raw source, used for copying — the rendered children carry highlight markup. */
  code: string
  children: React.ReactNode
}

export function CodeBlock({ language, code, children }: CodeBlockProps) {
  const { copied, copy } = useCopy()
  const [wrap, setWrap] = React.useState(false)

  return (
    <figure className="group relative my-4 overflow-hidden rounded-lg border border-border bg-muted/40">
      <figcaption className="flex items-center justify-between gap-2 border-b border-border bg-muted/60 px-3 py-1.5">
        <span className="font-mono text-xs text-muted-foreground">
          {language ?? 'text'}
        </span>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setWrap((value) => !value)}
            aria-pressed={wrap}
            title={wrap ? 'Disable soft wrap' : 'Enable soft wrap'}
          >
            <WrapText className={cn(wrap && 'text-primary')} />
            <span className="sr-only">
              {wrap ? 'Disable soft wrap' : 'Enable soft wrap'}
            </span>
          </Button>

          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => void copy(code, 'Code copied')}
          >
            {copied ? <Check className="text-emerald-500" /> : <Copy />}
            {/* The label changes on copy so screen readers hear the result. */}
            <span className="sr-only">
              {copied ? 'Code copied' : 'Copy code'}
            </span>
          </Button>
        </div>
      </figcaption>

      <pre
        className={cn(
          'scrollbar-thin m-0 overflow-x-auto bg-transparent p-4',
          wrap && 'whitespace-pre-wrap break-words',
        )}
        // Long code blocks are their own scroll region; keyboard users need to
        // be able to focus and scroll them without a mouse.
        tabIndex={0}
      >
        {children}
      </pre>
    </figure>
  )
}
