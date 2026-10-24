// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  questions: [] as Date[],
  chats: [] as Date[],
  keys: [] as Array<{ id: string; revokedAt: Date | null }>,
}))

const SECRETS = { AUTH_SECRET: 'auth-secret-value', AUTH_GITHUB_SECRET: 'github-secret-value' }

vi.mock('@/lib/auth', () => ({ oauthProvidersEnabled: () => ({ github: true, sso: false }) }))
vi.mock('@/lib/env', () => ({
  getEnv: () => ({
    ...SECRETS,
    AUTH_GITHUB_ID: 'github-id',
    AUTH_URL: 'http://localhost:8080',
    ALLOW_REGISTRATION: false,
    DEFAULT_MODEL: 'llama3.1',
    IDENTITY_ISSUER: 'llm-dev-kit-web',
    IDENTITY_AUDIENCE: 'llm-dev-kit',
    RAG_SERVICE_URL: 'http://rag.test',
    LLM_SERVICE_URL: 'http://llm.test',
  }),
}))
vi.mock('@/server/identity/tokens', () => ({
  mintAccessToken: vi.fn(async () => ({ token: 'admin-access-token', expiresIn: 300 })),
}))
vi.mock('@/server/http', () => {
  class ApiError extends Error {
    constructor(
      readonly code: string,
      message: string,
    ) {
      super(message)
    }
  }
  return { ApiError, notFound: (what: string) => new ApiError('not_found', `${what} not found`) }
})
vi.mock('@/lib/db', () => {
  const since = (rows: Date[], where: { createdAt: { gte: Date } }) =>
    rows.filter((at) => at >= where.createdAt.gte).map((createdAt) => ({ createdAt }))
  return {
    db: {
      user: { count: async () => 3, findMany: async () => [] },
      chat: {
        count: async () => state.chats.length,
        findMany: async ({ where }: { where: { createdAt: { gte: Date } } }) => since(state.chats, where),
      },
      message: {
        count: async () => 99,
        findMany: async ({ where }: { where: { role: string; createdAt: { gte: Date } } }) =>
          since(state.questions, where),
      },
      apiKey: {
        count: async () => 1,
        updateMany: async ({ where }: { where: { id: string; revokedAt: null } }) => {
          const key = state.keys.find((k) => k.id === where.id && !k.revokedAt)
          if (key) key.revokedAt = new Date()
          return { count: key ? 1 : 0 }
        },
      },
    },
  }
})

import {
  clearDocumentIndex,
  getConfig,
  getOverview,
  revokeAnyApiKey,
  uploadDocument,
} from '@/server/services/admin-service'

const NOW = new Date('2026-10-25T15:00:00Z')
const at = (iso: string) => new Date(iso)

function stubRag(responses: Record<string, () => Response>) {
  const calls: Array<{ url: string; init: RequestInit }> = []
  vi.stubGlobal('fetch', async (url: string, init: RequestInit) => {
    calls.push({ url, init })
    const path = url.replace('http://rag.test', '')
    const respond = responses[path]
    return respond ? respond() : new Response('not found', { status: 404 })
  })
  return calls
}

beforeEach(() => {
  vi.useFakeTimers({ now: NOW, toFake: ['Date'] })
  state.questions = []
  state.chats = []
  state.keys = [{ id: 'k1', revokedAt: null }]
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('getOverview', () => {
  it('buckets the last 14 UTC days, today last, and ignores older activity', async () => {
    state.questions = [
      at('2026-10-25T00:00:00Z'),
      at('2026-10-25T14:59:00Z'),
      at('2026-10-24T23:59:59Z'),
      at('2026-10-12T00:00:00Z'), // the first day in range
      at('2026-10-11T23:59:59Z'), // one second too old
    ]
    state.chats = [at('2026-10-25T09:00:00Z')]

    const { activity, counts } = await getOverview()

    expect(activity).toHaveLength(14)
    expect(activity[0]).toEqual({ date: '2026-10-12', messages: 1, chats: 0 })
    expect(activity[12]).toEqual({ date: '2026-10-24', messages: 1, chats: 0 })
    expect(activity[13]).toEqual({ date: '2026-10-25', messages: 2, chats: 1 })
    expect(activity.reduce((sum, day) => sum + day.messages, 0)).toBe(4)
    expect(counts.messages).toBe(99)
  })
})

describe('revokeAnyApiKey', () => {
  it("revokes anyone's active key once", async () => {
    await revokeAnyApiKey('k1')
    expect(state.keys[0]!.revokedAt).not.toBeNull()
    await expect(revokeAnyApiKey('k1')).rejects.toMatchObject({ code: 'not_found' })
    await expect(revokeAnyApiKey('ghost')).rejects.toMatchObject({ code: 'not_found' })
  })
})

describe('documents', () => {
  it("forward an upload with the admin's own token, then clear cached answers", async () => {
    const calls = stubRag({
      '/ingest/pdf': () => Response.json({ chunks: 7 }),
      '/cache/clear': () => Response.json({ cleared: 3 }),
    })
    const file = new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], 'handbook.pdf', {
      type: 'application/pdf',
    })

    expect(await uploadDocument('admin-1', file)).toEqual({
      filename: 'handbook.pdf',
      chunks: 7,
      cacheCleared: 3,
    })
    expect(calls.map((c) => c.url)).toEqual(['http://rag.test/ingest/pdf', 'http://rag.test/cache/clear'])
    expect(new Headers(calls[0]!.init.headers).get('authorization')).toBe('Bearer admin-access-token')
    expect((calls[0]!.init.body as FormData).get('file')).toBeInstanceOf(File)
  })

  it("pass the rag-service's own error through", async () => {
    stubRag({
      '/ingest/pdf': () =>
        Response.json(
          { error: { code: 'invalid_request', message: 'The PDF has no text layer' } },
          { status: 400 },
        ),
    })
    const file = new File(['x'], 'scan.pdf', { type: 'application/pdf' })
    await expect(uploadDocument('admin-1', file)).rejects.toMatchObject({
      code: 'invalid_request',
      message: 'The PDF has no text layer',
    })
  })

  it('report a clear that did not happen instead of pretending', async () => {
    stubRag({ '/documents/clear': () => Response.json({ cleared: false }) })
    await expect(clearDocumentIndex('admin-1')).rejects.toMatchObject({
      code: 'upstream_unavailable',
    })
  })

  it('say the rag-service is unreachable when it is', async () => {
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('fetch failed')
    })
    await expect(clearDocumentIndex('admin-1')).rejects.toMatchObject({
      code: 'upstream_unavailable',
    })
  })
})

describe('getConfig', () => {
  it('describes the instance without any secret', () => {
    const config = getConfig()
    expect(config.registrationOpen).toBe(false)
    expect(config.signIn).toEqual({ password: true, github: true, sso: false })
    const serialized = JSON.stringify(config)
    for (const secret of Object.values(SECRETS)) expect(serialized).not.toContain(secret)
  })
})
