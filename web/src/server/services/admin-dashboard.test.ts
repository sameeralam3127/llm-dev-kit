// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  questions: [] as Date[],
  chats: [] as Date[],
  keys: [] as Array<{ id: string; revokedAt: Date | null }>,
  audit: [] as Array<{ data: Record<string, unknown> }>,
  jobs: [] as Array<Record<string, unknown>>,
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
        findMany: async ({ where }: { where?: { createdAt: { gte: Date } } }) =>
          where?.createdAt ? since(state.chats, where) : [],
      },
      message: {
        count: async () => 99,
        findMany: async ({ where }: { where: { role: string; createdAt: { gte: Date } } }) =>
          since(state.questions, where),
      },
      apiKey: {
        count: async () => 1,
        findUnique: async ({ where }: { where: { id: string } }) =>
          state.keys.some((k) => k.id === where.id)
            ? { name: 'CI pipeline', prefix: 'sk-ldk-AbCd', user: { email: 'owner@example.test' } }
            : null,
        updateMany: async ({ where }: { where: { id: string; revokedAt: null } }) => {
          const key = state.keys.find((k) => k.id === where.id && !k.revokedAt)
          if (key) key.revokedAt = new Date()
          return { count: key ? 1 : 0 }
        },
      },
      auditEvent: { create: async (args: { data: Record<string, unknown> }) => void state.audit.push(args) },
      ingestionJob: {
        create: async ({ data }: { data: Record<string, unknown> }) => {
          const row = { id: `job-${state.jobs.length + 1}`, startedAt: new Date(), finishedAt: null, chunks: null, error: null, ...data }
          state.jobs.push(row)
          return { id: row.id }
        },
        update: async ({ where, data }: { where: { id: string }; data: Record<string, unknown> }) => {
          Object.assign(state.jobs.find((j) => j.id === where.id)!, data)
        },
        findMany: async () => [...state.jobs].reverse(),
      },
      $queryRaw: async () => [],
    },
  }
})

import {
  clearAnswerCache,
  clearDocumentIndex,
  getConfig,
  getOverview,
  getPluginInventory,
  listIngestionJobs,
  revokeAnyApiKey,
  uploadDocument,
} from '@/server/services/admin-service'

const ADMIN = { id: 'admin-1', email: 'admin@example.test' }
const actions = () => state.audit.map((entry) => entry.data['action'])

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
  state.audit = []
  state.jobs = []
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
    await revokeAnyApiKey(ADMIN, 'k1')
    expect(state.keys[0]!.revokedAt).not.toBeNull()
    await expect(revokeAnyApiKey(ADMIN, 'k1')).rejects.toMatchObject({ code: 'not_found' })
    await expect(revokeAnyApiKey(ADMIN, 'ghost')).rejects.toMatchObject({ code: 'not_found' })
  })

  it('records the revocation by name and prefix, never the key, and only when it happened', async () => {
    await revokeAnyApiKey(ADMIN, 'k1')
    await expect(revokeAnyApiKey(ADMIN, 'k1')).rejects.toBeDefined() // already revoked
    expect(actions()).toEqual(['api_key.revoked'])
    expect(state.audit[0]!.data).toMatchObject({ actorEmail: 'admin@example.test', target: 'api_key:k1' })
    expect(JSON.parse(state.audit[0]!.data['detail'] as string)).toEqual({
      name: 'CI pipeline',
      prefix: 'sk-ldk-AbCd',
      owner: 'owner@example.test',
    })
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

    expect(await uploadDocument(ADMIN, file)).toEqual({
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
    await expect(uploadDocument(ADMIN, file)).rejects.toMatchObject({
      code: 'invalid_request',
      message: 'The PDF has no text layer',
    })
  })

  it('track an upload as a job and audit it once, whatever else it triggers', async () => {
    stubRag({
      '/ingest/pdf': () => Response.json({ chunks: 7 }),
      '/cache/clear': () => Response.json({ cleared: 3 }),
    })
    await uploadDocument(ADMIN, new File(['%PDF-1.4'], 'handbook.pdf', { type: 'application/pdf' }))

    expect(state.jobs).toHaveLength(1)
    expect(state.jobs[0]).toMatchObject({
      filename: 'handbook.pdf',
      uploadedBy: 'admin@example.test',
      status: 'succeeded',
      chunks: 7,
    })
    expect(state.jobs[0]!['finishedAt']).toBeInstanceOf(Date)
    // The cache clear that follows an upload is part of it, not a second entry.
    expect(actions()).toEqual(['document.uploaded'])
    expect(state.audit[0]!.data['target']).toBe('handbook.pdf')
  })

  it('record a failed upload as a failed job and an audit entry, and still raise the error', async () => {
    stubRag({
      '/ingest/pdf': () =>
        Response.json({ error: { code: 'invalid_request', message: 'No text layer' } }, { status: 400 }),
    })
    await expect(
      uploadDocument(ADMIN, new File(['x'], 'scan.pdf', { type: 'application/pdf' })),
    ).rejects.toMatchObject({ code: 'invalid_request' })

    expect(state.jobs[0]).toMatchObject({ status: 'failed', error: 'No text layer' })
    expect(actions()).toEqual(['document.upload_failed'])
  })

  it('audit clearing the index and the cache, and nothing when the clear fails', async () => {
    stubRag({
      '/documents/clear': () => Response.json({ cleared: true }),
      '/cache/clear': () => Response.json({ cleared: 5 }),
    })
    await clearDocumentIndex(ADMIN)
    expect(await clearAnswerCache(ADMIN)).toBe(5)
    expect(actions()).toEqual(['document.index_cleared', 'cache.cleared'])

    state.audit = []
    stubRag({ '/documents/clear': () => Response.json({ cleared: false }) })
    await expect(clearDocumentIndex(ADMIN)).rejects.toBeDefined()
    expect(state.audit).toEqual([])
  })

  it('never put a token or file content in an audit entry', async () => {
    stubRag({ '/ingest/pdf': () => Response.json({ chunks: 1 }), '/cache/clear': () => Response.json({ cleared: 0 }) })
    await uploadDocument(ADMIN, new File(['SECRET-FILE-CONTENT'], 'a.pdf', { type: 'application/pdf' }))
    const stored = JSON.stringify(state.audit)
    expect(stored).not.toContain('admin-access-token')
    expect(stored).not.toContain('SECRET-FILE-CONTENT')
  })

  it('report a clear that did not happen instead of pretending', async () => {
    stubRag({ '/documents/clear': () => Response.json({ cleared: false }) })
    await expect(clearDocumentIndex(ADMIN)).rejects.toMatchObject({
      code: 'upstream_unavailable',
    })
  })

  it('say the rag-service is unreachable when it is', async () => {
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('fetch failed')
    })
    await expect(clearDocumentIndex(ADMIN)).rejects.toMatchObject({
      code: 'upstream_unavailable',
    })
  })
})

describe('listIngestionJobs', () => {
  it('shows a stale running job as interrupted, but a fresh one as running', async () => {
    const now = Date.now()
    state.jobs = [
      { id: 'old', filename: 'old.pdf', sizeBytes: 1, status: 'running', startedAt: new Date(now - 60 * 60_000), finishedAt: null, chunks: null, error: null, uploadedBy: null },
      { id: 'new', filename: 'new.pdf', sizeBytes: 1, status: 'running', startedAt: new Date(now - 30_000), finishedAt: null, chunks: null, error: null, uploadedBy: null },
    ]
    const jobs = await listIngestionJobs()
    expect(Object.fromEntries(jobs.map((job) => [job.id, job.status]))).toEqual({
      old: 'interrupted',
      new: 'running',
    })
  })
})

describe('getPluginInventory', () => {
  const row = (name: string) => ({
    kind: 'llm',
    name,
    version: '0.1.0',
    enabled: true,
    description: `The ${name} plugin`,
    permissions: ['network'],
  })

  it('merges every service, says which could not be asked, and sends the admin token', async () => {
    const seen: string[] = []
    vi.stubGlobal('fetch', async (url: string, init: RequestInit) => {
      seen.push(`${url} ${new Headers(init.headers).get('authorization')}`)
      if (url.startsWith('http://llm.test')) return Response.json([row('ollama'), row('openai')])
      throw new TypeError('fetch failed') // rag-service is down
    })

    const inventory = await getPluginInventory(ADMIN)

    expect(inventory.plugins.map((p) => `${p.service}:${p.name}`)).toEqual([
      'llm-service:ollama',
      'llm-service:openai',
    ])
    expect(inventory.unreachable).toEqual(['rag-service'])
    expect(seen).toContain('http://llm.test/plugins Bearer admin-access-token')
    expect(seen).toContain('http://rag.test/plugins Bearer admin-access-token')
  })

  it('treats a malformed answer as an unreachable service rather than trusting it', async () => {
    vi.stubGlobal('fetch', async () => Response.json({ not: 'a list' }))
    const inventory = await getPluginInventory(ADMIN)
    expect(inventory.plugins).toEqual([])
    expect(inventory.unreachable).toEqual(['llm-service', 'rag-service'])
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
