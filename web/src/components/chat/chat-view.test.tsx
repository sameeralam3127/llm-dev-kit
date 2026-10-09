import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render } from '@testing-library/react'
import * as React from 'react'
import { describe, expect, it, vi } from 'vitest'

import type { UseChatStreamResult } from '@/hooks/use-chat-stream'
import type { ChatDetail, ChatMessage } from '@/types/chat'

const mocks = vi.hoisted(() => {
  const markdownRenders = new Map<string, number>()
  const headerProps: Array<Record<string, unknown>> = []
  const composerProps: Array<Record<string, unknown>> = []
  const mutate = () => undefined

  // A tiny external store standing in for the streaming hook, so the test can
  // push "frames" the way useChatStream does: a new array with only the
  // growing message replaced.
  let state: { messages: ChatMessage[] } = { messages: [] }
  const listeners = new Set<() => void>()
  const store = {
    get: () => state,
    set: (messages: ChatMessage[]) => {
      state = { messages }
      for (const listener of listeners) listener()
    },
    subscribe: (listener: () => void) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
  const actions = {
    send: () => undefined,
    regenerate: () => undefined,
    editMessage: () => undefined,
    stop: () => undefined,
  }
  return { markdownRenders, headerProps, composerProps, mutate, store, actions }
})

// Counts how often each message body renders: a MessageItem that re-renders
// renders its Markdown again.
vi.mock('@/components/markdown/markdown', () => ({
  Markdown: ({ content }: { content: string }) => {
    mocks.markdownRenders.set(content, (mocks.markdownRenders.get(content) ?? 0) + 1)
    return <div>{content}</div>
  },
}))

// The real header and composer are memoised; what matters here is that the
// props they receive stay referentially equal from frame to frame.
vi.mock('@/components/chat/chat-header', () => ({
  ChatHeader: (props: Record<string, unknown>) => {
    mocks.headerProps.push(props)
    return null
  },
}))
vi.mock('@/components/chat/composer', () => ({
  Composer: (props: Record<string, unknown>) => {
    mocks.composerProps.push(props)
    return null
  },
}))

vi.mock('@/hooks/use-chats', () => ({ useUpdateChat: () => ({ mutate: mocks.mutate }) }))

vi.mock('@/hooks/use-chat-stream', () => ({
  useChatStream: (): UseChatStreamResult => {
    const { messages } = React.useSyncExternalStore(mocks.store.subscribe, mocks.store.get)
    return {
      messages,
      status: 'streaming',
      isLoading: false,
      error: null,
      isBusy: true,
      ...mocks.actions,
    }
  },
}))

import { ChatView } from '@/components/chat/chat-view'
import { TooltipProvider } from '@/components/ui/tooltip'

function message(id: string, role: 'user' | 'assistant', content: string, position: number) {
  return {
    id,
    chatId: 'chat-1',
    role,
    content,
    position,
    model: null,
    error: null,
    truncated: false,
    editedAt: null,
    createdAt: '2026-01-01T00:00:00.000Z',
    versions: [],
  } satisfies ChatMessage
}

const chat: ChatDetail = {
  id: 'chat-1',
  title: 'Test',
  model: 'llama3.1',
  pinned: false,
  archived: false,
  folderId: null,
  shareId: null,
  updatedAt: '2026-01-01T00:00:00.000Z',
  createdAt: '2026-01-01T00:00:00.000Z',
  messageCount: 3,
  systemPrompt: null,
  messages: [],
}

describe('ChatView while an answer streams', () => {
  it('re-renders only the growing message and keeps callbacks stable', () => {
    const history = [
      message('u1', 'user', 'First question', 0),
      message('a1', 'assistant', 'First answer', 1),
      message('u2', 'user', 'Second question', 2),
    ]
    mocks.store.set([...history, message('a2', 'assistant', 'Par', 3)])

    render(
      <QueryClientProvider client={new QueryClient()}>
        <TooltipProvider>
          <ChatView
            chat={{ ...chat, messages: mocks.store.get().messages }}
            user={{ name: 'Ada', image: null, email: 'ada@example.com' }}
          />
        </TooltipProvider>
      </QueryClientProvider>,
    )

    // Ten streamed frames: a new list each time, earlier messages unchanged.
    let content = 'Par'
    for (let frame = 0; frame < 10; frame++) {
      content += ` t${frame}`
      act(() => mocks.store.set([...history, message('a2', 'assistant', content, 3)]))
    }

    expect(mocks.markdownRenders.get('First answer')).toBe(1)
    expect(mocks.markdownRenders.get(content)).toBe(1)
    expect(mocks.composerProps.length).toBeGreaterThan(10)

    const first = { header: mocks.headerProps[0], composer: mocks.composerProps[0] }
    for (const props of mocks.headerProps) {
      expect(props.onModelChange).toBe(first.header?.onModelChange)
      expect(props.chat).toBe(first.header?.chat)
    }
    for (const props of mocks.composerProps) {
      expect(props.onSend).toBe(first.composer?.onSend)
      expect(props.onStop).toBe(first.composer?.onStop)
    }
  })
})
