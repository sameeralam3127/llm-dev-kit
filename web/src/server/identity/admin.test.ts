// @vitest-environment node
import { createHash } from 'node:crypto'

import type { Prisma } from '@prisma/client'
import { beforeEach, describe, expect, it } from 'vitest'

import { hashSetupCode, SETUP_ID } from '../../../prisma/setup-code.mjs'
import { claimFirstAdmin, ensureRolesStarted } from './admin'

interface SetupRow {
  id: string
  hash: string | null
  expiresAt: Date | null
}

interface UserRow {
  id: string
  role: string
  createdAt: Date
}

let users: UserRow[]
let setup: SetupRow | null

const client = {
  user: {
    findFirst: async ({ where }: { where?: { role: string } }) => {
      const ordered = [...users].sort(
        (a, b) => a.createdAt.getTime() - b.createdAt.getTime() || a.id.localeCompare(b.id),
      )
      return ordered.find((user) => !where || user.role === where.role) ?? null
    },
    update: async ({ where, data }: { where: { id: string }; data: { role: string } }) => {
      Object.assign(users.find((user) => user.id === where.id)!, data)
    },
  },
  setupCode: {
    findUnique: async () => setup,
    create: async ({ data }: { data: Omit<SetupRow, 'expiresAt'> }) => {
      setup = { ...data, expiresAt: null }
    },
    updateMany: async ({ where, data }: {
      where: { id: string; hash: string; expiresAt: { gt: Date } }
      data: { hash: null; expiresAt: null }
    }) => {
      if (
        !setup?.expiresAt ||
        setup.id !== where.id ||
        setup.hash !== where.hash ||
        setup.expiresAt <= where.expiresAt.gt
      ) {
        return { count: 0 }
      }

      setup = { ...setup, ...data }
      return { count: 1 }
    },
  },
} as unknown as Prisma.TransactionClient

const email = 'operator@example.test'
const code = 'synthetic-setup-code'
const issueCode = async (value: string, expiresAt: Date | null) => {
  setup = { id: SETUP_ID, hash: await hashSetupCode(value, email), expiresAt }
}

const user = (id: string, role = 'user', ageMs = 0) =>
  users.push({ id, role, createdAt: new Date(Date.now() - ageMs) })

const roles = () => Object.fromEntries(users.map((account) => [account.id, account.role]))

beforeEach(() => {
  users = []
  setup = null
})

describe('first administrator setup', () => {
  it('initializes a new instance without issuing a setup code', async () => {
    await ensureRolesStarted(client)
    expect(setup).toEqual({ id: SETUP_ID, hash: null, expiresAt: null })
    expect(users).toEqual([])
  })

  it('binds the digest to the intended email and spends the code once', async () => {
    await issueCode(code, new Date(Date.now() + 60_000))

    expect(setup?.hash).not.toContain(code)
    expect(await claimFirstAdmin(code, 'someone-else@example.test', client)).toBe(false)
    expect(await claimFirstAdmin('wrong-code', email, client)).toBe(false)
    expect(await claimFirstAdmin(code, ' Operator@Example.Test ', client)).toBe(true)
    expect(setup).toEqual({ id: SETUP_ID, hash: null, expiresAt: null })
    expect(await claimFirstAdmin(code, email, client)).toBe(false)
  })

  it('rejects expired codes and rejects codes issued by older versions', async () => {
    await issueCode(code, new Date(0))
    expect(await claimFirstAdmin(code, email, client)).toBe(false)

    setup = { id: SETUP_ID, hash: createHash('sha256').update(code).digest('hex'), expiresAt: null }
    expect(await claimFirstAdmin(code, email, client)).toBe(false)

    await issueCode(code, null)
    expect(await claimFirstAdmin(code, email, client)).toBe(false)
  })

  it('allows at most one concurrent claim of the pending code', async () => {
    await issueCode(code, new Date(Date.now() + 60_000))
    const claims = await Promise.all([
      claimFirstAdmin(code, email, client),
      claimFirstAdmin(code, email, client),
    ])
    expect(claims.filter(Boolean)).toHaveLength(1)
  })

  it('preserves a pending code through startup and rejects it once an admin exists', async () => {
    await issueCode(code, new Date(Date.now() + 60_000))
    user('ordinary')
    await ensureRolesStarted(client)
    expect(roles()).toEqual({ ordinary: 'user' })
    expect(setup?.hash).toBe(await hashSetupCode(code, email))

    user('existing-admin', 'admin')
    expect(await claimFirstAdmin(code, email, client)).toBe(false)
  })
})

describe('database from before roles existed', () => {
  it('promotes the earliest user once, and only then', async () => {
    user('newer', 'user', 1_000)
    user('oldest', 'user', 5_000)

    await ensureRolesStarted(client)
    expect(roles()).toEqual({ newer: 'user', oldest: 'admin' })

    user('later')
    await ensureRolesStarted(client)
    expect(roles()).toEqual({ newer: 'user', oldest: 'admin', later: 'user' })
  })

  it('leaves an install that already has an administrator alone', async () => {
    user('first', 'user', 5_000)
    user('boss', 'admin', 1_000)
    await ensureRolesStarted(client)
    expect(roles()).toEqual({ first: 'user', boss: 'admin' })
  })
})
