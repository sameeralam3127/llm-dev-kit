'use client'

import { Loader2 } from 'lucide-react'
import * as React from 'react'

import { Composer } from '@/components/chat/composer'
import { PromptSuggestions } from '@/components/chat/prompt-suggestions'
import { useCreateChat } from '@/hooks/use-chats'

/**
 * Landing view with no chat selected.
 *
 * Typing here creates the chat and hands the first message to the chat page via
 * sessionStorage, so the user never has to press "New chat" before they can
 * start typing. sessionStorage rather than a query string keeps the prompt out
 * of the URL, browser history, and any access logs in front of the app.
 */
export const PENDING_PROMPT_KEY = 'llm-dev-kit.pending-prompt'

export function NewChatLauncher() {
  const createChat = useCreateChat()
  const [isStarting, setIsStarting] = React.useState(false)

  const start = (content: string) => {
    if (isStarting) return
    setIsStarting(true)

    try {
      sessionStorage.setItem(PENDING_PROMPT_KEY, content)
    } catch {
      // Private-mode browsers can refuse storage; the chat still opens, the
      // user just has to send the message themselves.
    }

    createChat.mutate({}, { onError: () => setIsStarting(false) })
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        {isStarting ? (
          <div
            className="flex h-full flex-col items-center justify-center gap-3 text-muted-foreground"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="size-5 animate-spin" />
            <p className="text-sm">Starting your chat…</p>
          </div>
        ) : (
          <PromptSuggestions onSelect={start} disabled={createChat.isPending} />
        )}
      </div>

      <Composer
        onSend={start}
        onStop={() => undefined}
        isBusy={isStarting}
        placeholder="Ask anything to start a new chat…"
        autoFocus
      />

    </div>
  )
}
