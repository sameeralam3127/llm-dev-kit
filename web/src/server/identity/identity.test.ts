// @vitest-environment node
import { randomBytes } from 'node:crypto'

import { createLocalJWKSet, jwtVerify } from 'jose'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// ---------------------------------------------------------------- fakes

interface UserRow {
  id: string
  role: string
  createdAt: Date
}
interface KeyRow {
  id: string
  publicJwk: string
  privateJwk: string
  createdAt: Date
}
interface ApiKeyRow {
  id: string
  userId: string
  name: string
  prefix: string
  hash: string
  createdAt: Date
  lastUsedAt: Date | null
  revokedAt: Date | null
}

const state = vi.hoisted(() => ({
  users: [] as UserRow[],
  keys: [] as KeyRow[],
  apiKeys: [] as ApiKeyRow[],
  env: {
    AUTH_SECRET: '',
    IDENTITY_ISSUER: 'llm-dev-kit-web',
    IDENTITY_AUDIENCE: 'llm-dev-kit',
  },
}))

const pick = <T extends object>(row: T, select?: Record<string, boolean>) =>
  select
    ? (Object.fromEntries(Object.keys(select).map((k) => [k, row[k as keyof T]])) as Partial<T>)
    : row

vi.mock('@/lib/env', () => ({ getEnv: () => state.env }))

vi.mock('@/lib/db', () => {
  const byCreated = <T extends { createdAt: Date }>(rows: T[], dir: 'asc' | 'desc') =>
    [...rows].sort((a, b) =>
      dir === 'asc'
        ? a.createdAt.getTime() - b.createdAt.getTime()
        : b.createdAt.getTime() - a.createdAt.getTime(),
    )
  const db = {
    user: {
      findFirst: async ({ where, select }: { where?: { role?: string }; select?: Record<string, boolean> }) => {
        const rows = where?.role
          ? state.users.filter((u) => u.role === where.role)
          : byCreated(state.users, 'asc')
        return rows[0] ? pick(rows[0], select) : null
      },
      findUnique: async ({ where, select }: { where: { id: string }; select?: Record<string, boolean> }) => {
        const row = state.users.find((u) => u.id === where.id)
        return row ? pick(row, select) : null
      },
      update: async ({ where, data }: { where: { id: string }; data: Partial<UserRow> }) => {
        const row = state.users.find((u) => u.id === where.id)!
        Object.assign(row, data)
        return row
      },
    },
    signingKey: {
      findFirst: async () => byCreated(state.keys, 'desc')[0] ?? null,
      findMany: async ({ where }: { where: { createdAt: { gt: Date } } }) =>
        byCreated(state.keys, 'desc').filter((k) => k.createdAt > where.createdAt.gt),
      create: async ({ data }: { data: Omit<KeyRow, 'createdAt'> }) => {
        const row = { ...data, createdAt: new Date() }
        state.keys.push(row)
        return row
      },
      deleteMany: async ({ where }: { where: { createdAt: { lt: Date } } }) => {
        state.keys = state.keys.filter((k) => !(k.createdAt < where.createdAt.lt))
        return { count: 0 }
      },
    },
    apiKey: {
      count: async ({ where }: { where: { userId: string } }) =>
        state.apiKeys.filter((k) => k.userId === where.userId && !k.revokedAt).length,
      create: async ({ data }: { data: Pick<ApiKeyRow, 'userId' | 'name' | 'prefix' | 'hash'> }) => {
        const row: ApiKeyRow = {
          ...data,
          id: `key-${state.apiKeys.length + 1}`,
          createdAt: new Date(),
          lastUsedAt: null,
          revokedAt: null,
        }
        state.apiKeys.push(row)
        return row
      },
      findUnique: async ({ where }: { where: { hash: string } }) =>
        state.apiKeys.find((k) => k.hash === where.hash) ?? null,
      update: async ({ where, data }: { where: { id: string }; data: Partial<ApiKeyRow> }) => {
        Object.assign(state.apiKeys.find((k) => k.id === where.id)!, data)
      },
      updateMany: async ({ where, data }: { where: { id: string; userId: string }; data: Partial<ApiKeyRow> }) => {
        const row = state.apiKeys.find(
          (k) => k.id === where.id && k.userId === where.userId && !k.revokedAt,
        )
        if (row) Object.assign(row, data)
        return { count: row ? 1 : 0 }
      },
    },
  }
  return { db }
})

// `@/server/http` pulls in Auth.js; only ApiError is needed here.
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

import { createApiKey, resolveApiKey, revokeApiKey } from '@/server/identity/api-keys'
import { publishedKeys, resetSigningKeyCache, ROTATE_AFTER_MS } from '@/server/identity/keys'
import { open, seal } from '@/server/identity/secret-box'
import { mintAccessToken } from '@/server/identity/tokens'

const DAY = 24 * 60 * 60 * 1000

/** A fresh secret per test, as long as a real AUTH_SECRET. */
const randomSecret = () => randomBytes(32).toString('base64')

function user(id: string, role = 'user', ageDays = 0): UserRow {
  const row = { id, role, createdAt: new Date(Date.now() - ageDays * DAY) }
  state.users.push(row)
  return row
}

async function verify(token: string) {
  const jwks = createLocalJWKSet({ keys: await publishedKeys() })
  const { payload, protectedHeader } = await jwtVerify(token, jwks, {
    issuer: 'llm-dev-kit-web',
    audience: 'llm-dev-kit',
  })
  return { payload, protectedHeader }
}

beforeEach(() => {
  state.users = []
  state.keys = []
  state.apiKeys = []
  state.env.AUTH_SECRET = randomSecret()
  resetSigningKeyCache()
})

describe('secret box', () => {
  it('round-trips and refuses another secret', () => {
    const [a, b] = [randomSecret(), randomSecret()]
    const sealed = seal('private jwk', a)
    expect(sealed).not.toContain('private jwk')
    expect(open(sealed, a)).toBe('private jwk')
    expect(open(sealed, b)).toBeNull()
    expect(open('garbage', a)).toBeNull()
  })
})

describe('access tokens', () => {
  it('carry the role and its scopes, verifiable with the published keys', async () => {
    user('u1', 'viewer')
    const { token, expiresIn } = await mintAccessToken('u1')
    const { payload, protectedHeader } = await verify(token)

    expect(protectedHeader.alg).toBe('RS256')
    expect(payload.sub).toBe('u1')
    expect(payload.roles).toEqual(['viewer'])
    expect(payload.scope).toBe('chat')
    expect(payload.amr).toBeUndefined()
    expect(payload.exp! - payload.iat!).toBe(300)
    expect(expiresIn).toBe(300)
  })

  it('read the role from the database each time', async () => {
    const row = user('u1', 'admin')
    expect((await verify((await mintAccessToken('u1')).token)).payload.scope).toBe(
      'chat ingest admin',
    )
    row.role = 'user'
    expect((await verify((await mintAccessToken('u1')).token)).payload.scope).toBe('chat ingest')
  })

  it('mark tokens exchanged for an API key', async () => {
    user('u1')
    const { payload } = await verify((await mintAccessToken('u1', 'api_key')).token)
    expect(payload.amr).toEqual(['api_key'])
  })

  it('give an unknown stored role the least access', async () => {
    user('u1', 'superuser')
    const { payload } = await verify((await mintAccessToken('u1')).token)
    expect(payload.roles).toEqual(['viewer'])
  })

  it('refuse a user that no longer exists', async () => {
    await expect(mintAccessToken('ghost')).rejects.toMatchObject({ code: 'unauthorized' })
  })
})

describe('signing keys', () => {
  it('are stored with the private half encrypted', async () => {
    user('u1')
    await mintAccessToken('u1')
    expect(state.keys).toHaveLength(1)
    expect(state.keys[0]!.privateJwk).not.toContain('"d"')
    expect(JSON.parse(state.keys[0]!.publicJwk)).not.toHaveProperty('d')
  })

  it('rotate after 30 days and keep the old key published for a day more', async () => {
    user('u1')
    await mintAccessToken('u1')
    const old = state.keys[0]!
    old.createdAt = new Date(Date.now() - ROTATE_AFTER_MS - 60 * 60 * 1000)
    resetSigningKeyCache()

    const { protectedHeader } = await verify((await mintAccessToken('u1')).token)
    expect(protectedHeader.kid).not.toBe(old.id)
    // Tokens the old key signed just before rotating still verify.
    expect((await publishedKeys()).map((k) => k.kid)).toEqual([protectedHeader.kid, old.id])

    // A day after that, every token it signed has long expired.
    old.createdAt = new Date(Date.now() - ROTATE_AFTER_MS - DAY - 60_000)
    expect((await publishedKeys()).map((k) => k.kid)).toEqual([protectedHeader.kid])
  })

  it('rotate when AUTH_SECRET changes rather than fail', async () => {
    user('u1')
    await mintAccessToken('u1')
    state.env.AUTH_SECRET = randomSecret()
    resetSigningKeyCache()
    await verify((await mintAccessToken('u1')).token)
    expect(state.keys).toHaveLength(2)
  })
})

describe('API keys', () => {
  it('are shown once, stored hashed, and resolve to their owner', async () => {
    user('u1')
    const created = await createApiKey('u1', 'laptop')

    expect(created.key).toMatch(/^sk-ldk-[A-Za-z0-9_-]{43}$/)
    expect(created.prefix).toBe(created.key.slice(0, 11))
    expect(JSON.stringify(state.apiKeys)).not.toContain(created.key)

    expect(await resolveApiKey(created.key)).toBe('u1')
    expect(state.apiKeys[0]!.lastUsedAt).not.toBeNull()
  })

  it('stop working once revoked, and only their owner can revoke them', async () => {
    user('u1')
    user('u2')
    const { id, key } = await createApiKey('u1', 'ci')

    await expect(revokeApiKey('u2', id)).rejects.toMatchObject({ code: 'not_found' })
    expect(await resolveApiKey(key)).toBe('u1')

    await revokeApiKey('u1', id)
    expect(await resolveApiKey(key)).toBeNull()
  })

  it('reject anything that is not a key', async () => {
    expect(await resolveApiKey('sk-ldk-unknown')).toBeNull()
    expect(await resolveApiKey('sk-local')).toBeNull()
  })
})
