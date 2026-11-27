'use client'

import { BookOpen, Bug, FileText, PenLine, RefreshCw } from 'lucide-react'

import { BrandMark } from '@/components/brand/brand-mark'
import { Button } from '@/components/ui/button'
import { useServiceStatus } from '@/hooks/use-service-status'
import { cn } from '@/lib/utils'

// `description` says what the card does; `prompt` is what lands in the chat.
// They differ on purpose: "Draft something" starts an unfinished sentence for
// the user to complete, which made a poor card description.
const SUGGESTIONS = [
  {
    icon: FileText,
    title: 'Summarise my documents',
    description: 'Key points from the indexed documents, grouped by topic.',
    prompt:
      'Summarise the key points from the documents you have indexed, grouped by topic.',
  },
  {
    icon: Bug,
    title: 'Debug an error',
    description: 'Paste an error message and get the likely causes.',
    prompt:
      'I am seeing this error and cannot work out why:\n\n```\n\n```\n\nWhat are the likely causes?',
  },
  {
    icon: BookOpen,
    title: 'Explain a concept',
    description: 'How retrieval-augmented generation works, and when it beats fine-tuning.',
    prompt:
      'Explain how retrieval-augmented generation works, and when it beats fine-tuning.',
  },
  {
    icon: PenLine,
    title: 'Draft a release note',
    description: 'Describe a change in a sentence and get a concise note.',
    prompt: 'Draft a concise release note for a change that ',
  },
] as const

interface PromptSuggestionsProps {
  onSelect: (prompt: string) => void
  disabled?: boolean
}

export function PromptSuggestions({ onSelect, disabled }: PromptSuggestionsProps) {
  const { offline, refresh } = useServiceStatus()

  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col items-center justify-center px-6 py-12 text-center">
      <BrandMark size="lg" className="mb-6 animate-rise-in" />

      <h2
        className="animate-rise-in text-2xl font-semibold tracking-tight sm:text-3xl"
        style={{ animationDelay: '60ms' }}
      >
        What do you need to know?
      </h2>
      <p
        className="mt-3 max-w-md animate-rise-in text-sm leading-6 text-muted-foreground"
        style={{ animationDelay: '120ms' }}
      >
        Answers draw on the documents indexed for your workspace and list the
        passages they used, so you can check each claim.
      </p>

      {offline && (
        <div
          role="status"
          className="mt-6 flex w-full max-w-md items-start gap-3 rounded-lg border border-border bg-muted/40 px-4 py-3 text-left"
        >
          <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-destructive" aria-hidden="true" />
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium">The model host isn&rsquo;t responding</p>
            <p className="mt-0.5 text-muted-foreground">
              Questions can&rsquo;t be answered until it&rsquo;s back. This page checks again every
              30 seconds.
            </p>
          </div>
          <Button
            size="sm"
            variant="ghost"
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={() => void refresh()}
          >
            <RefreshCw />
            Check now
          </Button>
        </div>
      )}

      <ul className={cn('grid w-full gap-3 sm:grid-cols-2', offline ? 'mt-6' : 'mt-10')}>
        {SUGGESTIONS.map(({ icon: Icon, title, description, prompt }, index) => (
          <li
            key={title}
            className="animate-rise-in"
            style={{ animationDelay: `${200 + index * 70}ms` }}
          >
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(prompt)}
              className={cn(
                'group flex h-full w-full items-start gap-3 rounded-xl border bg-card p-4 text-left shadow-sm transition-colors',
                'hover:border-primary/40 hover:bg-accent/50',
                'disabled:cursor-not-allowed disabled:opacity-50',
              )}
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="size-4" />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold">{title}</span>
                <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
                  {description}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
