// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  /** Linked OAuth accounts, as "provider:providerAccountId". */
  accounts: new Set<string>(),
  /** Emails of existing users. */
  users: new Set<string>(),
  env: { ALLOW_REGISTRATION: true, AUTH_SSO_CREATE_USERS: false },
  lookups: 0,
}))

vi.mock('@/lib/db', () => ({
  db: {
    account: {
      findUnique: vi.fn(
        async ({ where }: { where: { provider_providerAccountId: { provider: string; providerAccountId: string } } }) => {
          state.lookups += 1
          const { provider, providerAccountId } = where.provider_providerAccountId
          return state.accounts.has(`${provider}:${providerAccountId}`) ? { id: 'acc' } : null
        },
      ),
    },
    user: {
      findUnique: vi.fn(async ({ where }: { where: { email: string } }) => {
        state.lookups += 1
        return state.users.has(where.email) ? { id: 'user' } : null
      }),
    },
  },
}))
vi.mock('@/lib/env', () => ({ getEnv: () => state.env }))

import { allowSignIn, mayCreateUser, REGISTRATION_CLOSED } from './registration'

const github = { type: 'oauth', provider: 'github', providerAccountId: '42' }
const sso = { type: 'oidc', provider: 'keycloak', providerAccountId: 'kc-7' }
const refused = `/login?error=${REGISTRATION_CLOSED}`

beforeEach(() => {
  state.accounts.clear()
  state.users.clear()
  state.env = { ALLOW_REGISTRATION: true, AUTH_SSO_CREATE_USERS: false }
  state.lookups = 0
})

describe('mayCreateUser', () => {
  it('lets any provider create users while registration is open', () => {
    expect(mayCreateUser('github', { ALLOW_REGISTRATION: true, AUTH_SSO_CREATE_USERS: false })).toBe(true)
    expect(mayCreateUser('keycloak', { ALLOW_REGISTRATION: true, AUTH_SSO_CREATE_USERS: false })).toBe(true)
  })

  it('lets only SSO create users while registration is closed, and only when allowed', () => {
    const closed = { ALLOW_REGISTRATION: false, AUTH_SSO_CREATE_USERS: false }
    expect(mayCreateUser('github', closed)).toBe(false)
    expect(mayCreateUser('keycloak', closed)).toBe(false)
    const ssoAllowed = { ALLOW_REGISTRATION: false, AUTH_SSO_CREATE_USERS: true }
    expect(mayCreateUser('keycloak', ssoAllowed)).toBe(true)
    expect(mayCreateUser('github', ssoAllowed)).toBe(false)
  })
})

describe('allowSignIn with registration closed', () => {
  beforeEach(() => {
    state.env = { ALLOW_REGISTRATION: false, AUTH_SSO_CREATE_USERS: false }
  })

  it('refuses a GitHub account that has never signed in here', async () => {
    expect(await allowSignIn(github, 'stranger@example.test')).toBe(refused)
  })

  it('still lets an already linked GitHub account in', async () => {
    state.accounts.add('github:42')
    expect(await allowSignIn(github, 'member@example.test')).toBe(true)
  })

  it('refuses a new SSO user unless AUTH_SSO_CREATE_USERS is on', async () => {
    expect(await allowSignIn(sso, 'new@example.test')).toBe(refused)
    state.env = { ALLOW_REGISTRATION: false, AUTH_SSO_CREATE_USERS: true }
    expect(await allowSignIn(sso, 'new@example.test')).toBe(true)
  })

  it('lets Auth.js refuse an email clash itself, with its clearer message', async () => {
    // No linked account, but the email belongs to a password user: Auth.js
    // creates nothing and fails with OAuthAccountNotLinked.
    state.users.add('member@example.test')
    expect(await allowSignIn(github, 'member@example.test')).toBe(true)
  })

  it('never blocks password sign-in, and does not touch the database for it', async () => {
    expect(await allowSignIn({ type: 'credentials', provider: 'credentials', providerAccountId: 'x' }, null)).toBe(true)
    expect(await allowSignIn(null, null)).toBe(true)
    expect(state.lookups).toBe(0)
  })
})

describe('allowSignIn with registration open', () => {
  it('lets a new GitHub account in, so it is created as today', async () => {
    expect(await allowSignIn(github, 'new@example.test')).toBe(true)
  })
})
