'use client'

import { BookOpen, Bug, FileText, Sparkles } from 'lucide-react'

import { cn } from '@/lib/utils'

const SUGGESTIONS = [
  {
    icon: FileText,
    title: 'Summarise my documents',
    prompt:
      'Summarise the key points from the documents you have indexed, grouped by topic.',
  },
  {
    icon: Bug,
    title: 'Debug an error',
    prompt:
      'I am seeing this error and cannot work out why:\n\n```\n\n```\n\nWhat are the likely causes?',
  },
  {
    icon: BookOpen,
    title: 'Explain a concept',
    prompt:
      'Explain how retrieval-augmented generation works, and when it beats fine-tuning.',
  },
  {
    icon: Sparkles,
    title: 'Draft something',
    prompt: 'Draft a concise release note for a change that ',
  },
] as const

interface PromptSuggestionsProps {
  onSelect: (prompt: string) => void
  disabled?: boolean
}

export function PromptSuggestions({ onSelect, disabled }: PromptSuggestionsProps) {
  return (
    <div className="mx-auto flex h-full w-full max-w-3xl flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-violet-500 text-white shadow-sm">
        <Sparkles className="size-6" />
      </div>

      <h2 className="text-xl font-semibold tracking-tight">
        What can I help you with?
      </h2>
      <p className="mt-1.5 max-w-md text-sm text-muted-foreground">
        Ask anything. Answers are grounded in the documents indexed by your
        retrieval service.
      </p>

      <ul className="mt-8 grid w-full gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map(({ icon: Icon, title, prompt }) => (
          <li key={title}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(prompt)}
              className={cn(
                'group flex h-full w-full items-start gap-3 rounded-xl border border-border bg-card p-3.5 text-left transition-all',
                'hover:-translate-y-0.5 hover:border-primary/40 hover:bg-accent hover:shadow-md focus-visible:border-primary/40',
                'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-none',
              )}
            >
              <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
              <span className="min-w-0">
                <span className="block text-sm font-medium">{title}</span>
                <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
                  {prompt.replace(/```/g, '').trim()}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
