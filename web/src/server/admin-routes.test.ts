/// <reference types="vite/client" />
// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * The exit criterion of #17: every admin API refuses non-admins on the
 * server. Route files are discovered, not listed, so a new admin route is
 * covered the moment it exists.
 */

const state = vi.hoisted(() => ({
  session: null as { user: { id: string; email: string } } | null,
  roles: { 'admin-1': 'admin', 'user-1': 'user', 'viewer-1': 'viewer' } as Record<string, string>,
}))

vi.mock('@/lib/auth', () => ({ auth: async () => state.session }))
vi.mock('@/lib/db', () => ({
  db: {
    user: {
      findUnique: async ({ where }: { where: { id: string } }) =>
        state.roles[where.id] ? { role: state.roles[where.id] } : null,
    },
  },
}))

const service = vi.hoisted(() => ({
  listUsers: vi.fn(async () => []),
  setUserRole: vi.fn(async () => ({ id: 'user-1', role: 'viewer' })),
  getHealth: vi.fn(async () => ({ checks: [] })),
  getOverview: vi.fn(async () => ({ counts: {}, activity: [], recentUsers: [] })),
  listAllApiKeys: vi.fn(async () => []),
  revokeAnyApiKey: vi.fn(async () => undefined),
  getDocumentStats: vi.fn(async () => ({})),
  uploadDocument: vi.fn(async () => ({ filename: 'a.pdf', chunks: 1, cacheCleared: 0 })),
  clearDocumentIndex: vi.fn(async () => ({ cacheCleared: 0 })),
  clearAnswerCache: vi.fn(async () => 0),
}))
vi.mock('@/server/services/admin-service', () => service)

type Handler = (request: Request, context: { params: Promise<Record<string, string>> }) => Promise<Response>

const routes = import.meta.glob<Record<string, unknown>>('/src/app/api/admin/**/route.ts', {
  eager: true,
})
const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] as const

const handlers = Object.entries(routes).flatMap(([file, module]) =>
  METHODS.filter((method) => typeof module[method] === 'function').map((method) => ({
    name: `${method} ${file.replace('/src/app', '').replace('/route.ts', '')}`,
    method,
    call: module[method] as Handler,
  })),
)

function invoke(handler: (typeof handlers)[number]) {
  const init: RequestInit = { method: handler.method }
  if (handler.name === 'POST /api/admin/documents') {
    const form = new FormData()
    form.append('file', new File(['%PDF-1.7'], 'a.pdf', { type: 'application/pdf' }))
    init.body = form
  } else if (handler.method !== 'GET') {
    init.body = JSON.stringify({ role: 'viewer' })
    init.headers = { 'Content-Type': 'application/json' }
  }
  return handler.call(new Request('http://app.test/api/admin', init), {
    params: Promise.resolve({ userId: 'user-1', keyId: 'key-1' }),
  })
}

function signIn(id: string | null) {
  state.session = id ? { user: { id, email: `${id}@example.test` } } : null
}

beforeEach(() => {
  vi.clearAllMocks()
  signIn(null)
})

describe('admin API routes', () => {
  it('are discovered', () => {
    expect(handlers.map((h) => h.name).sort()).toEqual([
      'DELETE /api/admin/api-keys/[keyId]',
      'GET /api/admin/api-keys',
      'GET /api/admin/documents',
      'GET /api/admin/health',
      'GET /api/admin/overview',
      'GET /api/admin/users',
      'PATCH /api/admin/users/[userId]',
      'POST /api/admin/cache/clear',
      'POST /api/admin/documents',
      'POST /api/admin/documents/clear',
    ])
  })

  it.each(handlers.map((h) => [h.name, h] as const))('%s: 401 without a session', async (_, h) => {
    expect((await invoke(h)).status).toBe(401)
  })

  it.each(handlers.map((h) => [h.name, h] as const))(
    '%s: 403 for a user and a viewer, and nothing runs',
    async (_, h) => {
      for (const id of ['user-1', 'viewer-1']) {
        signIn(id)
        const res = await invoke(h)
        expect(res.status).toBe(403)
        expect(((await res.json()) as { error: { code: string } }).error.code).toBe('forbidden')
      }
      for (const fn of Object.values(service)) expect(fn).not.toHaveBeenCalled()
    },
  )

  it.each(handlers.map((h) => [h.name, h] as const))('%s: allowed for an admin', async (_, h) => {
    signIn('admin-1')
    const res = await invoke(h)
    expect(res.ok, `status ${res.status}`).toBe(true)
  })

  it('refuses an upload that is not a PDF before calling the rag-service', async () => {
    signIn('admin-1')
    const upload = handlers.find((h) => h.name === 'POST /api/admin/documents')!
    const form = new FormData()
    form.append('file', new File(['hello'], 'notes.txt', { type: 'text/plain' }))
    const res = await upload.call(
      new Request('http://app.test/api/admin/documents', { method: 'POST', body: form }),
      { params: Promise.resolve({}) },
    )
    expect(res.status).toBe(400)
    expect(service.uploadDocument).not.toHaveBeenCalled()
  })

  it('reads the role from the database, not the session', async () => {
    signIn('admin-1')
    state.roles['admin-1'] = 'user'
    const users = handlers.find((h) => h.name === 'GET /api/admin/users')!
    expect((await invoke(users)).status).toBe(403)
    state.roles['admin-1'] = 'admin'
  })
})
