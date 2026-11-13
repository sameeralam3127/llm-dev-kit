// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

const db = vi.hoisted(() => ({
  user: { count: vi.fn(), findMany: vi.fn() },
  chat: { count: vi.fn(), findMany: vi.fn() },
  message: { count: vi.fn(), findMany: vi.fn() },
  apiKey: { count: vi.fn() },
  $queryRaw: vi.fn(),
}))

vi.mock('@/lib/db', () => ({ db }))
vi.mock('@/lib/env', () => ({
  getEnv: () => ({
    ALLOW_REGISTRATION: true,
    DEFAULT_MODEL: 'llama3.1',
    IDENTITY_ISSUER: 'iss',
    IDENTITY_AUDIENCE: 'aud',
    RAG_SERVICE_URL: 'http://rag.test',
    LLM_SERVICE_URL: 'http://llm.test',
    GRAFANA_URL: 'http://grafana.test',
  }),
}))
vi.mock('@/lib/auth', () => ({ oauthProvidersEnabled: () => ({ github: false, sso: false }) }))
vi.mock('@/server/identity/tokens', () => ({ mintAccessToken: vi.fn() }))
vi.mock('@/server/http', () => ({
  ApiError: class extends Error {},
  notFound: (what: string) => new Error(`${what} not found`),
}))

import { RATE_LIMITS } from '@/server/rate-limit'
import { getConfig, getOverview, toUsageRows, USAGE_ROWS } from './admin-service'

beforeEach(() => {
  vi.clearAllMocks()
  db.user.count.mockResolvedValue(2)
  db.user.findMany.mockResolvedValue([])
  db.chat.count.mockResolvedValue(3)
  db.chat.findMany.mockResolvedValue([])
  db.message.count.mockResolvedValue(12)
  db.message.findMany.mockResolvedValue([])
  db.apiKey.count.mockResolvedValue(1)
})

describe('usage by user and model', () => {
  it('is grouped, sorted and bounded in the database, not in memory', async () => {
    db.$queryRaw.mockResolvedValue([
      { userId: 'u2', name: null, email: 'grace@example.test', model: 'openai/gpt-4o', chats: 1, messages: 9 },
      { userId: 'u1', name: 'Ada', email: 'ada@example.test', model: 'llama3.1', chats: 2n, messages: 6n },
    ])

    const overview = await getOverview()

    // One aggregate query; chats are never loaded row by row for usage.
    expect(db.$queryRaw).toHaveBeenCalledTimes(1)
    const [strings, ...values] = db.$queryRaw.mock.calls[0] as [TemplateStringsArray, ...unknown[]]
    const sql = strings.join('?')
    expect(sql).toMatch(/GROUP BY/)
    expect(sql).toMatch(/ORDER BY "messages" DESC/)
    expect(values).toEqual([USAGE_ROWS])
    expect(db.chat.findMany).not.toHaveBeenCalledWith(
      expect.objectContaining({ select: expect.objectContaining({ _count: expect.anything() }) }),
    )

    expect(overview.usage).toEqual([
      { userId: 'u2', user: 'grace@example.test', email: 'grace@example.test', model: 'openai/gpt-4o', chats: 1, messages: 9 },
      { userId: 'u1', user: 'Ada', email: 'ada@example.test', model: 'llama3.1', chats: 2, messages: 6 },
    ])
    expect(overview).not.toHaveProperty('activeSessions')
  })

  it('accepts the bigint counts Postgres returns, and falls back to the email for a name', () => {
    expect(
      toUsageRows([{ userId: 'u', name: null, email: 'x@example.test', model: 'm', chats: 3n, messages: 40n }]),
    ).toEqual([{ userId: 'u', user: 'x@example.test', email: 'x@example.test', model: 'm', chats: 3, messages: 40 }])
  })
})

describe('configuration shown to admins', () => {
  it('lists exactly the rate limits the routes enforce', () => {
    const { rateLimits } = getConfig()
    expect(rateLimits).toEqual([
      { name: 'Sign-up', limit: RATE_LIMITS.register.limit, windowSeconds: 3600, per: 'IP address' },
      { name: 'Chat messages', limit: RATE_LIMITS.chat.limit, windowSeconds: 60, per: 'user' },
      { name: 'API key exchange', limit: RATE_LIMITS.tokenExchange.limit, windowSeconds: 60, per: 'IP address' },
    ])
  })

  it('includes the dashboard link from GRAFANA_URL', () => {
    expect(getConfig().dashboardUrl).toBe('http://grafana.test')
  })
})
