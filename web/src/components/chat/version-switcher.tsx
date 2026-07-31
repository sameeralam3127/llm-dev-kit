'use client'

import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'

interface VersionSwitcherProps {
  index: number
  total: number
  onChange: (index: number) => void
}

/** Pages through regenerated answers, newest last. */
export function VersionSwitcher({ index, total, onChange }: VersionSwitcherProps) {
  if (total <= 1) return null

  return (
    <div
      className="flex items-center gap-0.5"
      role="group"
      aria-label="Response versions"
    >
      <Button
        variant="ghost"
        size="icon-sm"
        disabled={index === 0}
        onClick={() => onChange(index - 1)}
      >
        <ChevronLeft />
        <span className="sr-only">Previous version</span>
      </Button>

      <span className="min-w-10 text-center text-xs tabular-nums text-muted-foreground">
        <span className="sr-only">Version </span>
        {index + 1} / {total}
      </span>

      <Button
        variant="ghost"
        size="icon-sm"
        disabled={index === total - 1}
        onClick={() => onChange(index + 1)}
      >
        <ChevronRight />
        <span className="sr-only">Next version</span>
      </Button>
    </div>
  )
}
