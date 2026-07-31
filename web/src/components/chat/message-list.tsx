'use client'

import { ArrowDown } from 'lucide-react'
import * as React from 'react'

import { MessageItem } from '@/components/chat/message-item'
import { Button } from '@/components/ui/button'
import { useStickToBottom } from '@/hooks/use-stick-to-bottom'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/types/chat'

interface MessageListProps {
  messages: ChatMessage[]
  isStreaming: boolean
  isBusy: boolean
  readOnly?: boolean
  user?: { name: string | null; image: string | null; email: string | null }
  onEdit?: (messageId: string, content: string) => void
  onRegenerate?: (messageId: string) => void
  onDelete?: (messageId: string) => void
  emptyState?: React.ReactNode
}

export function MessageList({
  messages,
  isStreaming,
  isBusy,
  readOnly = false,
  user,
  onEdit,
  onRegenerate,
  onDelete,
  emptyState,
}: MessageListProps) {
  const lastMessage = messages.at(-1)

  // Re-pin on every content change of the trailing message, which is what grows
  // while a response streams.
  const { ref, isPinned, scrollToBottom } = useStickToBottom<HTMLDivElement>(
    `${messages.length}:${lastMessage?.content.length ?? 0}`,
  )

  if (messages.length === 0 && emptyState) {
    return <div className="flex-1 overflow-y-auto">{emptyState}</div>
  }

  return (
    <div className="relative flex-1 overflow-hidden">
      <div
        ref={ref}
        className="scrollbar-thin h-full overflow-y-auto"
        // A labelled region lets screen-reader users jump straight to the
        // transcript; `feed` conveys that entries are appended over time.
        role="feed"
        aria-busy={isBusy}
        aria-label="Conversation"
        tabIndex={0}
      >
        <div className="mx-auto w-full max-w-3xl divide-y divide-border/60">
          {messages.map((message, index) => (
            <MessageItem
              key={message.id}
              message={message}
              isStreaming={isStreaming && index === messages.length - 1}
              isBusy={isBusy}
              readOnly={readOnly}
              {...(user ? { user } : {})}
              {...(onEdit ? { onEdit } : {})}
              {...(onRegenerate ? { onRegenerate } : {})}
              {...(onDelete ? { onDelete } : {})}
            />
          ))}
        </div>

        {/* Breathing room so the last message clears the composer. */}
        <div className="h-6" aria-hidden="true" />
      </div>

      {/* Only offered once the reader has actually scrolled away. */}
      <div
        className={cn(
          'pointer-events-none absolute inset-x-0 bottom-4 flex justify-center transition-opacity',
          isPinned ? 'opacity-0' : 'opacity-100',
        )}
      >
        <Button
          variant="secondary"
          size="sm"
          onClick={() => scrollToBottom()}
          tabIndex={isPinned ? -1 : 0}
          aria-hidden={isPinned}
          className={cn(
            'gap-1.5 rounded-full border border-border shadow-md',
            !isPinned && 'pointer-events-auto',
          )}
        >
          <ArrowDown className="size-3.5" />
          Latest
        </Button>
      </div>
    </div>
  )
}
