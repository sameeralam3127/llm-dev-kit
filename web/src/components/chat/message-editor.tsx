'use client'

import * as React from 'react'

import { Button } from '@/components/ui/button'
import { LIMITS } from '@/lib/constants'

interface MessageEditorProps {
  initialContent: string
  onSubmit: (content: string) => void
  onCancel: () => void
}

/**
 * Inline editor for a user message. Saving rewinds the conversation to this
 * turn and regenerates, so the button says so plainly.
 */
export function MessageEditor({
  initialContent,
  onSubmit,
  onCancel,
}: MessageEditorProps) {
  const [value, setValue] = React.useState(initialContent)
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  React.useEffect(() => {
    const element = textareaRef.current
    if (!element) return

    element.focus()
    // Caret at the end rather than selecting everything — most edits are a
    // small amendment, not a full rewrite.
    element.setSelectionRange(element.value.length, element.value.length)
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 400)}px`
  }, [])

  const changed = value.trim() !== initialContent.trim()
  const canSave = value.trim().length > 0 && changed

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault()
      onCancel()
      return
    }

    if (
      (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) ||
      (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing)
    ) {
      event.preventDefault()
      if (canSave) onSubmit(value)
    }
  }

  return (
    <div className="w-full">
      <label htmlFor="message-editor" className="sr-only">
        Edit your message
      </label>
      <textarea
        id="message-editor"
        ref={textareaRef}
        value={value}
        onChange={(event) => {
          setValue(event.target.value.slice(0, LIMITS.messageMaxChars))
          const element = event.currentTarget
          element.style.height = 'auto'
          element.style.height = `${Math.min(element.scrollHeight, 400)}px`
        }}
        onKeyDown={handleKeyDown}
        rows={2}
        className="scrollbar-thin w-full resize-none rounded-lg border border-input bg-background px-3 py-2 text-[0.9375rem] leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />

      <div className="mt-2 flex items-center justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button size="sm" disabled={!canSave} onClick={() => onSubmit(value)}>
          Save &amp; regenerate
        </Button>
      </div>
    </div>
  )
}
