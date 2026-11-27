// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'

import { OpenAICompatibleProvider } from '@/lib/llm/openai-compatible'

const mocks = vi.hoisted(() => ({
  finalizeAssistantMessage: vi.fn(async () => undefined),
}))

vi.mock('@/lib/auth', () => ({ auth: async () => ({ user: { id: 'user-1' } }) }))
vi.mock('@/lib/db', () => ({ db: {} }))
vi.mock('@/lib/llm', () => ({
  backendOptions: async () => ({}),
  noteModelHost: () => undefined,
  getChatProvider: () => new OpenAICompatibleProvider({ baseUrl: 'http://rag.test/v1', timeoutMs: 5000 }),
}))
vi.mock('@/server/services/chat-service', () => ({
  prepareTurn: async () => ({
    chatId: 'chat-1',
    title: 'Test chat',
    userMessage: { id: 'message-1' },
    assistantMessageId: 'message-2',
    model: 'test-model',
    providerMessages: [{ role: 'user', content: 'Test question' }],
  }),
  finalizeAssistantMessage: mocks.finalizeAssistantMessage,
}))

import { POST } from './route'

function chatRequest() {
  return new Request('http://app.test/api/chat', {
    method: 'POST',
    body: JSON.stringify({ chatId: 'chat-1', intent: 'send', content: 'Test question' }),
  })
}

afterEach(() => {
  vi.clearAllMocks()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('stream failures', () => {
  it('keeps partial output and stores only a failure code', async () => {
    const canary = 'synthetic-backend-error-detail'
    vi.stubGlobal('fetch', async () => new Response(
      `data: ${JSON.stringify({ choices: [{ delta: { content: 'Partial answer' } }] })}\n\n` +
      `data: ${JSON.stringify({ error: { message: canary } })}\n\n`,
    ))

    const body = await (await POST(chatRequest())).text()
    expect(body).not.toContain(canary)
    expect(body).toContain('The upstream service could not complete the request')
    expect(mocks.finalizeAssistantMessage).toHaveBeenCalledWith(expect.objectContaining({
      content: 'Partial answer',
      errorCode: 'upstream_error',
      truncated: true,
    }))
  })

  it('keeps database exception details out of logs and responses', async () => {
    const canary = 'synthetic-database-error-detail'
    mocks.finalizeAssistantMessage.mockRejectedValueOnce(new Error(canary))
    vi.stubGlobal('fetch', async () => new Response('data: [DONE]\n\n'))
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    const body = await (await POST(chatRequest())).text()
    expect(body).not.toContain(canary)
    expect(log.mock.calls).toEqual([['[chat] failed to persist assistant message']])
  })
})
