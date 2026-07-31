'use client'

import { ArrowUp, Square } from 'lucide-react'
import * as React from 'react'

import { Button } from '@/components/ui/button'
import { LIMITS } from '@/lib/constants'
import { cn } from '@/lib/utils'

const MAX_TEXTAREA_HEIGHT = 240

interface ComposerProps {
  onSend: (content: string) => void
  onStop: () => void
  isBusy: boolean
  disabled?: boolean
  placeholder?: string
  autoFocus?: boolean
}

export function Composer({
  onSend,
  onStop,
  isBusy,
  disabled = false,
  placeholder = 'Send a message…',
  autoFocus = false,
}: ComposerProps) {
  const [value, setValue] = React.useState('')
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const resize = React.useCallback(() => {
    const element = textareaRef.current
    if (!element) return

    // Collapse first so the scrollHeight reflects the content, not the old box.
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`
    element.style.overflowY =
      element.scrollHeight > MAX_TEXTAREA_HEIGHT ? 'auto' : 'hidden'
  }, [])

  React.useEffect(resize, [value, resize])

  const canSend = value.trim().length > 0 && !isBusy && !disabled
  const remaining = LIMITS.messageMaxChars - value.length
  const showCounter = remaining < 500

  const submit = () => {
    if (!canSend) return
    onSend(value)
    setValue('')
    // Return focus so a follow-up can be typed straight away.
    requestAnimationFrame(() => textareaRef.current?.focus())
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter inserts a newline. `isComposing` guards IME
    // users, for whom Enter commits the candidate rather than the message.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-border bg-background/80 backdrop-blur">
      <form
        className="mx-auto w-full max-w-3xl px-4 py-3 sm:px-6"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <div
          className={cn(
            'flex items-end gap-2 rounded-2xl border border-input bg-background p-2 shadow-sm transition-colors',
            'focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30',
            disabled && 'opacity-60',
          )}
        >
          <label htmlFor="composer-input" className="sr-only">
            Message
          </label>
          <textarea
            id="composer-input"
            ref={textareaRef}
            value={value}
            onChange={(event) => setValue(event.target.value.slice(0, LIMITS.messageMaxChars))}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            autoFocus={autoFocus}
            rows={1}
            aria-describedby="composer-hint"
            className="scrollbar-thin max-h-60 flex-1 resize-none bg-transparent px-2 py-1.5 text-[0.9375rem] leading-6 outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
          />

          {isBusy ? (
            <Button
              type="button"
              size="icon"
              variant="secondary"
              onClick={onStop}
              className="shrink-0 rounded-xl"
            >
              <Square className="fill-current" />
              <span className="sr-only">Stop generating</span>
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon"
              disabled={!canSend}
              className="shrink-0 rounded-xl"
            >
              <ArrowUp />
              <span className="sr-only">Send message</span>
            </Button>
          )}
        </div>

        <div className="mt-1.5 flex items-center justify-between px-1">
          <p id="composer-hint" className="text-xs text-muted-foreground">
            <kbd className="font-sans font-medium">Enter</kbd> to send ·{' '}
            <kbd className="font-sans font-medium">Shift</kbd> +{' '}
            <kbd className="font-sans font-medium">Enter</kbd> for a new line
          </p>

          {showCounter && (
            <p
              className={cn(
                'text-xs tabular-nums',
                remaining <= 0 ? 'text-destructive' : 'text-muted-foreground',
              )}
              // Announce politely so it does not interrupt typing.
              aria-live="polite"
            >
              {remaining.toLocaleString()} left
            </p>
          )}
        </div>
      </form>
    </div>
  )
}
