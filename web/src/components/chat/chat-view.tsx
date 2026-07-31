'use client'

import { useQueryClient } from '@tanstack/react-query'
import * as React from 'react'

import { ChatHeader } from '@/components/chat/chat-header'
import { Composer } from '@/components/chat/composer'
import { MessageList } from '@/components/chat/message-list'
import { PENDING_PROMPT_KEY } from '@/components/chat/new-chat-launcher'
import { PromptSuggestions } from '@/components/chat/prompt-suggestions'
import { MessageListSkeleton } from '@/components/skeletons/message-skeleton'
import { api, queryKeys } from '@/lib/api-client'
import { useChatStream } from '@/hooks/use-chat-stream'
import { useUpdateChat } from '@/hooks/use-chats'
import type { ChatDetail } from '@/types/chat'

interface ChatViewProps {
  chat: ChatDetail
  user: { name: string | null; image: string | null; email: string | null }
}

export function ChatView({ chat, user }: ChatViewProps) {
  const queryClient = useQueryClient()
  const updateChat = useUpdateChat()

  const [model, setModel] = React.useState(chat.model)

  const {
    messages,
    status,
    isLoading,
    send,
    regenerate,
    editMessage,
    stop,
    isBusy,
  } = useChatStream({ chatId: chat.id, initialData: chat })

  // Server data is authoritative after a navigation between chats.
  React.useEffect(() => {
    setModel(chat.model)
  }, [chat.id, chat.model])

  // A prompt typed on the landing screen before this chat existed. Read once
  // and cleared immediately so a refresh cannot replay it.
  const sendRef = React.useRef(send)
  sendRef.current = send

  React.useEffect(() => {
    if (chat.messages.length > 0) return

    let pending: string | null = null
    try {
      pending = sessionStorage.getItem(PENDING_PROMPT_KEY)
      if (pending) sessionStorage.removeItem(PENDING_PROMPT_KEY)
    } catch {
      return
    }

    if (pending?.trim()) sendRef.current(pending, chat.model)
  }, [chat.id, chat.messages.length, chat.model])

  const handleModelChange = (next: string) => {
    setModel(next)
    // Persist the choice so returning to this chat keeps it, rather than
    // silently reverting to whatever it was created with.
    updateChat.mutate({ chatId: chat.id, input: { model: next } })
  }

  const handleDelete = async (messageId: string) => {
    await api.chats.removeMessage(chat.id, messageId)
    await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chat.id) })
  }

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <ChatHeader
        chat={chat}
        model={model}
        onModelChange={handleModelChange}
        isBusy={isBusy}
      />

      {isLoading ? (
        <div className="flex-1 overflow-y-auto">
          <MessageListSkeleton />
        </div>
      ) : (
        <MessageList
          messages={messages}
          isStreaming={status === 'streaming' || status === 'submitting'}
          isBusy={isBusy}
          user={user}
          onEdit={(messageId, content) => editMessage(messageId, content, model)}
          onRegenerate={(messageId) => regenerate(messageId, model)}
          onDelete={(messageId) => void handleDelete(messageId)}
          emptyState={
            <PromptSuggestions
              onSelect={(prompt) => send(prompt, model)}
              disabled={isBusy}
            />
          }
        />
      )}

      <Composer
        onSend={(content) => send(content, model)}
        onStop={stop}
        isBusy={isBusy}
        autoFocus
      />
    </div>
  )
}
