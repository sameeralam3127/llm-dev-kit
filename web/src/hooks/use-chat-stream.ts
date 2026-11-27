'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { api, queryKeys } from '@/lib/api-client'
import { streamChat } from '@/lib/stream-client'
import { isAbortError, tempId } from '@/lib/utils'
import type { ChatDetail, ChatMessage, SendMessagePayload } from '@/types/chat'

export type StreamStatus = 'idle' | 'submitting' | 'streaming'

interface UseChatStreamOptions {
  chatId: string
  /** Server-rendered detail, used as the initial cache entry to avoid a flash. */
  initialData?: ChatDetail
}

export interface UseChatStreamResult {
  /** The latest server detail; titles change after the first answer. */
  chat: ChatDetail | undefined
  messages: ChatMessage[]
  status: StreamStatus
  isLoading: boolean
  error: Error | null
  send: (content: string, model?: string) => void
  regenerate: (messageId?: string, model?: string) => void
  editMessage: (messageId: string, content: string, model?: string) => void
  stop: () => void
  isBusy: boolean
}

function emptyMessage(
  chatId: string,
  role: 'user' | 'assistant',
  content: string,
  position: number,
): ChatMessage {
  return {
    id: tempId(role),
    chatId,
    role,
    content,
    position,
    model: null,
    error: null,
    truncated: false,
    sources: [],
    editedAt: null,
    createdAt: new Date().toISOString(),
    versions: [],
  }
}

export function useChatStream({
  chatId,
  initialData,
}: UseChatStreamOptions): UseChatStreamResult {
  const queryClient = useQueryClient()

  const {
    data,
    isLoading,
    error: queryError,
  } = useQuery({
    queryKey: queryKeys.chat(chatId),
    queryFn: ({ signal }) => api.chats.get(chatId, signal),
    ...(initialData ? { initialData } : {}),
    staleTime: 30_000,
  })

  const [messages, setMessages] = useState<ChatMessage[]>(
    () => initialData?.messages ?? [],
  )
  const [status, setStatus] = useState<StreamStatus>('idle')
  const [error, setError] = useState<Error | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const statusRef = useRef<StreamStatus>('idle')
  statusRef.current = status

  // Server data owns the list whenever nothing is in flight. Refusing to sync
  // mid-stream is what stops a background refetch from wiping the tokens that
  // have arrived but are not yet persisted.
  useEffect(() => {
    if (data && statusRef.current === 'idle') {
      setMessages(data.messages)
    }
  }, [data])

  // Switching chats must not leave the previous stream writing into the new one.
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      abortRef.current = null
    }
  }, [chatId])

  const runTurn = useCallback(
    async (payload: SendMessagePayload, optimistic: (prev: ChatMessage[]) => ChatMessage[]) => {
      if (statusRef.current !== 'idle') return

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setError(null)
      setStatus('submitting')
      statusRef.current = 'submitting'
      setMessages(optimistic)

      let assistantId: string | null = null

      const revertOptimistic = () => {
        const persisted = queryClient.getQueryData<ChatDetail>(queryKeys.chat(chatId))
        setMessages(persisted?.messages ?? [])
      }

      // A failure before the server created the turn has no message to hang an
      // error card on: put the list back as the server has it and say so once.
      // After that, the error lives on the answer itself, where Retry is.
      const fail = (message: string) => {
        const failedId = assistantId
        if (failedId) {
          setMessages((prev) =>
            prev.map((entry) => (entry.id === failedId ? { ...entry, error: message } : entry)),
          )
        } else {
          revertOptimistic()
          toast.error('Message not sent', { description: message })
        }
        setError(new Error(message))
      }

      let pending = ''
      let frame: number | null = null

      // Tokens arrive far faster than the screen refreshes. Buffer them and
      // commit once per animation frame; without this a fast local model turns
      // into hundreds of renders a second and the tab stutters.
      const flush = () => {
        frame = null
        if (!pending || !assistantId) return

        const chunk = pending
        pending = ''
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? { ...message, content: message.content + chunk }
              : message,
          ),
        )
      }

      const scheduleFlush = () => {
        frame ??= requestAnimationFrame(flush)
      }

      try {
        for await (const event of streamChat(payload, controller.signal)) {
          switch (event.type) {
            case 'meta': {
              assistantId = event.assistantMessageId
              setStatus('streaming')
              statusRef.current = 'streaming'
              // Swap optimistic ids for the persisted ones so later actions
              // (copy link, regenerate, delete) address real rows.
              setMessages((prev) =>
                prev.map((message) => {
                  if (message.id.startsWith('user_')) {
                    return { ...message, id: event.userMessageId }
                  }
                  if (message.id.startsWith('assistant_')) {
                    return { ...message, id: event.assistantMessageId }
                  }
                  return message
                }),
              )
              break
            }

            case 'sources': {
              const sourcedId = assistantId
              setMessages((prev) =>
                prev.map((message) =>
                  message.id === sourcedId ? { ...message, sources: event.sources } : message,
                ),
              )
              break
            }

            case 'delta': {
              pending += event.text
              scheduleFlush()
              break
            }

            case 'done': {
              if (frame !== null) cancelAnimationFrame(frame)
              flush()
              const finalId = assistantId
              setMessages((prev) =>
                prev.map((message) =>
                  message.id === finalId
                    ? { ...message, content: event.content, truncated: event.truncated }
                    : message,
                ),
              )
              break
            }

            case 'error': {
              if (frame !== null) cancelAnimationFrame(frame)
              flush()
              fail(event.message)
              break
            }
          }
        }
      } catch (caught) {
        if (frame !== null) cancelAnimationFrame(frame)
        if (isAbortError(caught)) {
          // Stopped before the server took the turn: nothing was saved, so an
          // empty answer bubble would only be a dead end.
          if (!assistantId) revertOptimistic()
        } else {
          fail(caught instanceof Error ? caught.message : 'Something went wrong')
        }
      } finally {
        if (frame !== null) cancelAnimationFrame(frame)
        setStatus('idle')
        statusRef.current = 'idle'
        abortRef.current = null

        // Pull the authoritative rows (ids, versions, truncation) and refresh
        // the sidebar, whose titles and ordering just changed.
        void queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) })
        void queryClient.invalidateQueries({ queryKey: ['chats'] })
        // The server notes what this turn showed about the backend; let the
        // status line catch up now rather than on its next poll.
        void queryClient.invalidateQueries({ queryKey: queryKeys.status() })
      }
    },
    [chatId, queryClient],
  )

  const send = useCallback(
    (content: string, model?: string) => {
      const trimmed = content.trim()
      if (!trimmed) return

      void runTurn(
        {
          chatId,
          intent: 'send',
          content: trimmed,
          ...(model ? { model } : {}),
        },
        (prev) => {
          const nextPosition = (prev.at(-1)?.position ?? -1) + 1
          return [
            ...prev,
            emptyMessage(chatId, 'user', trimmed, nextPosition),
            emptyMessage(chatId, 'assistant', '', nextPosition + 1),
          ]
        },
      )
    },
    [chatId, runTurn],
  )

  const regenerate = useCallback(
    (messageId?: string, model?: string) => {
      void runTurn(
        {
          chatId,
          intent: 'regenerate',
          ...(messageId ? { targetMessageId: messageId } : {}),
          ...(model ? { model } : {}),
        },
        (prev) => {
          const targetIndex = messageId
            ? prev.findIndex((message) => message.id === messageId)
            : prev.map((message) => message.role).lastIndexOf('assistant')
          if (targetIndex === -1) return prev

          // Drop anything after the answer being replaced — the server does the
          // same, and showing stale follow-ups mid-regeneration is confusing.
          return prev.slice(0, targetIndex + 1).map((message, index) =>
            index === targetIndex
              ? { ...message, content: '', error: null, truncated: false }
              : message,
          )
        },
      )
    },
    [chatId, runTurn],
  )

  const editMessage = useCallback(
    (messageId: string, content: string, model?: string) => {
      const trimmed = content.trim()
      if (!trimmed) return

      void runTurn(
        {
          chatId,
          intent: 'edit',
          targetMessageId: messageId,
          content: trimmed,
          ...(model ? { model } : {}),
        },
        (prev) => {
          const targetIndex = prev.findIndex((message) => message.id === messageId)
          if (targetIndex === -1) return prev

          const target = prev[targetIndex]
          if (!target) return prev

          return [
            ...prev.slice(0, targetIndex),
            {
              ...target,
              content: trimmed,
              editedAt: new Date().toISOString(),
            },
            emptyMessage(chatId, 'assistant', '', target.position + 1),
          ]
        },
      )
    },
    [chatId, runTurn],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  return {
    chat: data,
    messages,
    status,
    isLoading: isLoading && messages.length === 0,
    error: error ?? (queryError as Error | null) ?? null,
    send,
    regenerate,
    editMessage,
    stop,
    isBusy: status !== 'idle',
  }
}
