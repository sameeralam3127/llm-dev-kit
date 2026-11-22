// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

interface UserRow {
  id: string
  role: string
  createdAt: Date
}
interface SetupRow {
  id: string
  hash: string | null
}

const state = vi.hoisted(() => ({
  users: [] as UserRow[],
  setup: null as SetupRow | null,
}))

vi.mock('@/lib/db', () => {
  const byCreated = (rows: UserRow[]) =>
    [...rows].sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime() || a.id.localeCompare(b.id))
  const db = {
    user: {
      findFirst: async ({ where }: { where?: { role?: string } } = {}) => {
        const rows = where?.role ? state.users.filter((u) => u.role === where.role) : byCreated(state.users)
        return rows[0] ? { id: rows[0].id } : null
      },
      update: async ({ where, data }: { where: { id: string }; data: Partial<UserRow> }) => {
        Object.assign(state.users.find((u) => u.id === where.id)!, data)
      },
    },
    setupCode: {
      findUnique: async () => (state.setup ? { ...state.setup } : null),
      create: async ({ data }: { data: { id: string; hash?: string | null } }) => {
        state.setup = { id: data.id, hash: data.hash ?? null }
        return state.setup
      },
      update: async ({ data }: { data: { hash: string | null } }) => {
        state.setup = { ...state.setup!, hash: data.hash }
        return state.setup
      },
      updateMany: async ({ where, data }: { where: { id: string; hash: string }; data: { hash: null } }) => {
        const match = state.setup?.id === where.id && state.setup.hash === where.hash
        if (match) state.setup = { ...state.setup!, hash: data.hash }
        return { count: match ? 1 : 0 }
      },
    },
  }
  return { db }
})

import { bootstrapAdmin, claimFirstAdmin, hashSetupCode } from './admin'

const user = (id: string, role = 'user', ageMs = 0) =>
  state.users.push({ id, role, createdAt: new Date(Date.now() - ageMs) })

const roles = () => Object.fromEntries(state.users.map((u) => [u.id, u.role]))

beforeEach(() => {
  state.users = []
  state.setup = null
})

describe('fresh instance', () => {
  it('issues a setup code and stores only its hash', async () => {
    const code = await bootstrapAdmin()

    expect(code).toMatch(/^[A-Za-z0-9_-]{32}$/)
    expect(state.setup!.hash).toBe(hashSetupCode(code!))
    expect(state.setup!.hash).not.toContain(code!)
  })

  it('makes no admin on its own, and a sign-up without the code is a plain user', async () => {
    await bootstrapAdmin()
    expect(await claimFirstAdmin(undefined)).toBe(false)
    expect(state.users).toEqual([])
  })

  it('lets exactly one sign-up with the code become admin', async () => {
    const code = (await bootstrapAdmin())!

    expect(await claimFirstAdmin('not-the-code')).toBe(false)
    expect(state.setup!.hash).not.toBeNull()

    expect(await claimFirstAdmin(code)).toBe(true)
    expect(state.setup!.hash).toBeNull()
    expect(await claimFirstAdmin(code)).toBe(false)
  })
})

describe('restart', () => {
  it('promotes nobody when users exist without an admin, and rotates the code', async () => {
    const first = (await bootstrapAdmin())!
    user('stranger', 'user', 5_000)
    user('operator', 'user', 1_000)

    const second = (await bootstrapAdmin())!

    expect(roles()).toEqual({ stranger: 'user', operator: 'user' })
    expect(second).not.toBe(first)
    expect(await claimFirstAdmin(first)).toBe(false)
    expect(await claimFirstAdmin(second)).toBe(true)
  })

  it('leaves an install that already has an admin alone', async () => {
    user('oldest', 'user', 5_000)
    user('boss', 'admin', 1_000)

    expect(await bootstrapAdmin()).toBeNull()
    expect(roles()).toEqual({ oldest: 'user', boss: 'admin' })
    expect(await claimFirstAdmin('anything')).toBe(false)
  })

  it('stops a code working once an admin exists by other means', async () => {
    const code = (await bootstrapAdmin())!
    user('promoted', 'admin')

    expect(await claimFirstAdmin(code)).toBe(false)
  })
})

describe('database from before roles existed', () => {
  it('promotes the earliest user once, and only then', async () => {
    user('newer', 'user', 1_000)
    user('oldest', 'user', 5_000)

    expect(await bootstrapAdmin()).toBeNull()
    expect(roles()).toEqual({ newer: 'user', oldest: 'admin' })

    user('later', 'user', 0)
    expect(await bootstrapAdmin()).toBeNull()
    expect(roles()).toEqual({ newer: 'user', oldest: 'admin', later: 'user' })
  })
})
