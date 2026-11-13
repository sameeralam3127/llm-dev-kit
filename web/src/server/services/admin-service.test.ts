// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  users: [] as Array<{ id: string; role: string; createdAt: Date }>,
  audit: [] as Array<{ data: Record<string, unknown> }>,
  failAudit: false,
}))

vi.mock('@/lib/env', () => ({ getEnv: () => ({}) }))
vi.mock('@/lib/auth', () => ({ oauthProvidersEnabled: () => ({ github: false, sso: false }) }))
vi.mock('@/server/identity/tokens', () => ({ mintAccessToken: vi.fn() }))
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
  const user = {
    findUnique: async ({ where }: { where: { id: string } }) => {
      const row = state.users.find((u) => u.id === where.id)
      return row ? { ...row, email: `${row.id}@example.test` } : null
    },
    count: async ({ where }: { where: { role: string } }) =>
      state.users.filter((u) => u.role === where.role).length,
    update: async ({ where, data }: { where: { id: string }; data: { role: string } }) => {
      Object.assign(state.users.find((u) => u.id === where.id)!, data)
    },
    findMany: async () =>
      state.users.map((u) => ({
        ...u,
        name: null,
        email: `${u.id}@example.test`,
        passwordHash: 'x',
        accounts: [],
        _count: { chats: 0, apiKeys: 0 },
      })),
  }
  const auditEvent = {
    create: async (args: { data: Record<string, unknown> }) => {
      if (state.failAudit) throw new Error('audit table unavailable')
      state.audit.push(args)
    },
  }
  // A transaction that rolls back: changes are undone when the callback throws.
  const db = {
    user,
    auditEvent,
    $transaction: async (fn: (tx: unknown) => unknown) => {
      const before = state.users.map((u) => ({ ...u }))
      const auditBefore = state.audit.length
      try {
        return await fn({ user, auditEvent })
      } catch (error) {
        state.users = before
        state.audit.length = auditBefore
        throw error
      }
    },
  }
  return { db }
})

import { setUserRole } from '@/server/services/admin-service'

const ADMIN = { id: 'boss', email: 'boss@example.test' }

beforeEach(() => {
  state.audit = []
  state.failAudit = false
  state.users = [
    { id: 'boss', role: 'admin', createdAt: new Date(1) },
    { id: 'pat', role: 'user', createdAt: new Date(2) },
  ]
})

describe('setUserRole', () => {
  it('changes a role', async () => {
    expect((await setUserRole(ADMIN, 'pat', 'viewer')).role).toBe('viewer')
  })

  it('never removes the last admin, not even at their own request', async () => {
    await expect(setUserRole(ADMIN, 'boss', 'user')).rejects.toMatchObject({ code: 'conflict' })
    expect(state.users[0]!.role).toBe('admin')
  })

  it('lets an admin step down once there is another', async () => {
    await setUserRole(ADMIN, 'pat', 'admin')
    expect((await setUserRole(ADMIN, 'boss', 'user')).role).toBe('user')
  })

  it('refuses an unknown user', async () => {
    await expect(setUserRole(ADMIN, 'ghost', 'user')).rejects.toMatchObject({ code: 'not_found' })
  })
})

describe('setUserRole audit trail', () => {
  it('records who changed whose role, from what to what', async () => {
    await setUserRole(ADMIN, 'pat', 'viewer')
    expect(state.audit).toHaveLength(1)
    expect(state.audit[0]!.data).toMatchObject({
      actorId: 'boss',
      actorEmail: 'boss@example.test',
      action: 'user.role_changed',
      target: 'user:pat',
    })
    expect(JSON.parse(state.audit[0]!.data['detail'] as string)).toEqual({
      email: 'pat@example.test',
      from: 'user',
      to: 'viewer',
    })
  })

  it('records nothing for a change that changes nothing, or one that is refused', async () => {
    await setUserRole(ADMIN, 'pat', 'user')
    await expect(setUserRole(ADMIN, 'boss', 'user')).rejects.toMatchObject({ code: 'conflict' })
    expect(state.audit).toEqual([])
  })

  it('rolls the change back when its entry cannot be written', async () => {
    state.failAudit = true
    await expect(setUserRole(ADMIN, 'pat', 'viewer')).rejects.toThrow('audit table unavailable')
    expect(state.users.find((u) => u.id === 'pat')!.role).toBe('user')
  })
})
