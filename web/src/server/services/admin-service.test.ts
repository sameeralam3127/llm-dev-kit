// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  users: [] as Array<{ id: string; role: string; createdAt: Date }>,
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
    findUnique: async ({ where }: { where: { id: string } }) =>
      state.users.find((u) => u.id === where.id) ?? null,
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
  const db = { user, $transaction: async (fn: (tx: unknown) => unknown) => fn({ user }) }
  return { db }
})

import { setUserRole } from '@/server/services/admin-service'

beforeEach(() => {
  state.users = [
    { id: 'boss', role: 'admin', createdAt: new Date(1) },
    { id: 'pat', role: 'user', createdAt: new Date(2) },
  ]
})

describe('setUserRole', () => {
  it('changes a role', async () => {
    expect((await setUserRole('pat', 'viewer')).role).toBe('viewer')
  })

  it('never removes the last admin, not even at their own request', async () => {
    await expect(setUserRole('boss', 'user')).rejects.toMatchObject({ code: 'conflict' })
    expect(state.users[0]!.role).toBe('admin')
  })

  it('lets an admin step down once there is another', async () => {
    await setUserRole('pat', 'admin')
    expect((await setUserRole('boss', 'user')).role).toBe('user')
  })

  it('refuses an unknown user', async () => {
    await expect(setUserRole('ghost', 'user')).rejects.toMatchObject({ code: 'not_found' })
  })
})
