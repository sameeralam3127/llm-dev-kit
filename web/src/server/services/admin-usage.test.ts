// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'

const db = vi.hoisted(() => ({
  user: { count: vi.fn(), findMany: vi.fn() },
  chat: { count: vi.fn(), findMany: vi.fn() },
  message: { count: vi.fn(), findMany: vi.fn() },
  apiKey: { count: vi.fn() },
  session: { count: vi.fn() },
}))

vi.mock('@/lib/db', () => ({ db }))
vi.mock('@/lib/env', () => ({ getEnv: () => ({}) }))
vi.mock('@/lib/auth', () => ({ oauthProvidersEnabled: () => ({ github: false, sso: false }) }))
vi.mock('@/server/identity/tokens', () => ({ mintAccessToken: vi.fn() }))
vi.mock('@/server/http', () => ({
  ApiError: class extends Error {},
  notFound: (what: string) => new Error(`${what} not found`),
}))

import { getOverview } from './admin-service'

describe('getOverview usage', () => {
  it('groups chats by user and model and reports active sessions', async () => {
    db.user.count.mockResolvedValue(2)
    db.user.findMany.mockResolvedValue([])
    db.chat.count.mockResolvedValueOnce(3).mockResolvedValueOnce(1)
    db.message.count.mockResolvedValue(12)
    db.apiKey.count.mockResolvedValue(1)
    db.message.findMany.mockResolvedValue([])
    db.chat.findMany
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          userId: 'u1',
          model: 'llama3.1',
          user: { name: 'Ada', email: 'ada@example.test' },
          _count: { messages: 4 },
        },
        {
          userId: 'u1',
          model: 'llama3.1',
          user: { name: 'Ada', email: 'ada@example.test' },
          _count: { messages: 2 },
        },
        {
          userId: 'u2',
          model: 'openai/gpt-4o',
          user: { name: null, email: 'grace@example.test' },
          _count: { messages: 9 },
        },
      ])
    db.session.count.mockResolvedValue(2)

    const overview = await getOverview()

    expect(overview.activeSessions).toBe(2)
    expect(overview.usage).toEqual([
      {
        userId: 'u2',
        user: 'grace@example.test',
        email: 'grace@example.test',
        model: 'openai/gpt-4o',
        chats: 1,
        messages: 9,
      },
      {
        userId: 'u1',
        user: 'Ada',
        email: 'ada@example.test',
        model: 'llama3.1',
        chats: 2,
        messages: 6,
      },
    ])
  })
})
