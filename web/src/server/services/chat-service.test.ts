// @vitest-environment jsdom
import { createElement, Fragment } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MessageItem } from '@/components/chat/message-item'

const OLD_QUESTION = 'Old question with customer account details'
const CURRENT_QUESTION = 'What is the deployment status?'
const OLD_ANSWER = 'Previous answer with an internal access token'
const CURRENT_ANSWER = 'The deployment is healthy.'

const mocks = vi.hoisted(() => {
  const oldQuestion = 'Old question with customer account details'
  const currentQuestion = 'What is the deployment status?'
  const oldAnswer = 'Previous answer with an internal access token'
  const currentAnswer = 'The deployment is healthy.'
  const createdAt = new Date('2026-10-25T08:46:52.000Z')
  const questionVersion = {
    id: 'version-question-1',
    messageId: 'message-question',
    content: oldQuestion,
    model: null,
    position: 0,
    createdAt,
  }
  const answerVersion = {
    id: 'version-answer-1',
    messageId: 'message-answer',
    content: oldAnswer,
    model: 'test-model',
    position: 0,
    createdAt,
  }
  const messages = [
    {
      id: 'message-question',
      chatId: 'chat-1',
      role: 'user',
      content: currentQuestion,
      position: 0,
      model: null,
      error: null,
      truncated: false,
      editedAt: createdAt,
      createdAt,
      versions: [questionVersion],
    },
    {
      id: 'message-answer',
      chatId: 'chat-1',
      role: 'assistant',
      content: currentAnswer,
      position: 1,
      model: 'test-model',
      error: null,
      truncated: false,
      editedAt: null,
      createdAt,
      versions: [answerVersion],
    },
  ]
  const chat = {
    id: 'chat-1',
    title: 'Deployment status',
    model: 'test-model',
    pinned: false,
    archived: false,
    folderId: null,
    shareId: 'share-1',
    updatedAt: createdAt,
    createdAt,
    sharedAt: createdAt,
    systemPrompt: null,
    _count: { messages: messages.length },
  }
  const materializeChat = (includeVersions: boolean) => ({
    ...chat,
    messages: messages.map(({ versions: messageVersions, ...message }) => ({
      ...message,
      ...(includeVersions ? { versions: messageVersions } : {}),
    })),
  })
  const calls: { shared: unknown[]; private: unknown[] } = { shared: [], private: [] }
  const findUnique = vi.fn(
    async (args: { include: { messages: { include?: { versions?: unknown } } } }) => {
      calls.shared.push(args)
      return materializeChat(Boolean(args.include.messages.include?.versions))
    },
  )
  const findFirst = vi.fn(
    async (args: { include: { messages: { include?: { versions?: unknown } } } }) => {
      calls.private.push(args)
      return materializeChat(Boolean(args.include.messages.include?.versions))
    },
  )

  return { calls, chat: { findFirst, findUnique } }
})

vi.mock('@/lib/db', () => ({ db: { chat: mocks.chat } }))
vi.mock('@/lib/env', () => ({ getEnv: () => ({ DEFAULT_MODEL: 'test-model' }) }))
vi.mock('@/server/http', () => {
  class ApiError extends Error {
    constructor(
      readonly code: string,
      message: string,
    ) {
      super(message)
    }
  }
  return {
    ApiError,
    badRequest: (message: string) => new ApiError('invalid_request', message),
    notFound: (what: string) => new ApiError('not_found', `${what} not found`),
  }
})

import { getChat, getSharedChat } from '@/server/services/chat-service'

beforeEach(() => {
  vi.clearAllMocks()
  mocks.calls.shared.length = 0
  mocks.calls.private.length = 0
})

describe('getSharedChat', () => {
  it('omits archived message versions from the shared payload and rendered messages', async () => {
    const chat = await getSharedChat('share-1')

    expect(chat?.messages.map((message) => message.versions)).toEqual([[], []])
    expect(JSON.stringify(chat)).not.toContain(OLD_QUESTION)
    expect(JSON.stringify(chat)).not.toContain(OLD_ANSWER)
    expect(mocks.calls.shared[0]).not.toHaveProperty('include.messages.include')

    const renderedHtml = renderToStaticMarkup(
      createElement(
        Fragment,
        null,
        ...(chat?.messages.map((message) =>
          createElement(MessageItem, {
            key: message.id,
            message,
            readOnly: true,
          }),
        ) ?? []),
      ),
    )

    expect(renderedHtml).toContain(CURRENT_QUESTION)
    expect(renderedHtml).toContain(CURRENT_ANSWER)
    expect(renderedHtml).not.toContain(OLD_QUESTION)
    expect(renderedHtml).not.toContain(OLD_ANSWER)
  })
})

describe('getChat', () => {
  it("continues loading archived versions for the owner's chat", async () => {
    const chat = await getChat('owner-1', 'chat-1')

    expect(chat.messages.map((message) => message.versions.map((version) => version.content))).toEqual([
      [OLD_QUESTION],
      [OLD_ANSWER],
    ])
    expect(mocks.calls.private[0]).toHaveProperty('include.messages.include.versions')
  })
})
