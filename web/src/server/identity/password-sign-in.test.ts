// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// next-auth's entry imports Next.js server internals that do not load under
// vitest. CredentialsSignin is re-exported from @auth/core, so use that class.
vi.mock('next-auth', async () => ({
  CredentialsSignin: (await import('@auth/core/errors')).CredentialsSignin,
}))

import { authorizePassword, SIGN_IN_LIMITS, TooManySignInAttempts } from './password-sign-in'

const PASSWORD = 'correct horse battery'
const USER = { id: 'u1', name: 'Ada', email: 'ada@example.test', image: null, passwordHash: 'hash' }

let n = 0
/** A fresh email and address per test: the limiter is process-wide. */
function fresh() {
  n += 1
  return { email: `user${n}@example.test`, ip: `10.0.${Math.floor(n / 250)}.${n % 250}` }
}
function request(ip: string): Request {
  return new Request('http://localhost/api/auth/callback/credentials', { headers: { 'x-real-ip': ip } })
}

function deps(email: string) {
  return {
    findUser: vi.fn(async (e: string) => (e === email ? { ...USER, email } : null)),
    compare: vi.fn(async (plain: string, hash: string) => hash === 'hash' && plain === PASSWORD),
    dummyHash: 'dummy',
  }
}

beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => {})
})
afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('authorizePassword', () => {
  it('signs in with the right password', async () => {
    const { email, ip } = fresh()
    const d = deps(email)
    expect(await authorizePassword({ email, password: PASSWORD }, request(ip), d)).toMatchObject({ id: 'u1', email })
  })

  it('refuses the attempt after five failures for one email, without running bcrypt', async () => {
    const { email, ip } = fresh()
    const d = deps(email)
    for (let i = 0; i < SIGN_IN_LIMITS.perEmail.limit; i++) {
      expect(await authorizePassword({ email, password: 'wrong' }, request(ip), d)).toBeNull()
    }
    expect(d.compare).toHaveBeenCalledTimes(SIGN_IN_LIMITS.perEmail.limit)
    await expect(authorizePassword({ email, password: PASSWORD }, request(ip), d)).rejects.toBeInstanceOf(
      TooManySignInAttempts,
    )
    expect(d.compare).toHaveBeenCalledTimes(SIGN_IN_LIMITS.perEmail.limit)
  })

  it('keeps counting one email across rotating client addresses', async () => {
    const { email } = fresh()
    const d = deps(email)
    for (let i = 0; i < SIGN_IN_LIMITS.perEmail.limit; i++) {
      await authorizePassword({ email, password: 'wrong' }, request(fresh().ip), d)
    }
    await expect(authorizePassword({ email, password: PASSWORD }, request(fresh().ip), d)).rejects.toBeInstanceOf(
      TooManySignInAttempts,
    )
  })

  it('counts unknown emails too, so the limit says nothing about which accounts exist', async () => {
    const { email } = fresh()
    const d = deps('someone-else@example.test')
    for (let i = 0; i < SIGN_IN_LIMITS.perEmail.limit; i++) {
      expect(await authorizePassword({ email, password: 'x' }, request(fresh().ip), d)).toBeNull()
    }
    await expect(authorizePassword({ email, password: 'x' }, request(fresh().ip), d)).rejects.toBeInstanceOf(
      TooManySignInAttempts,
    )
  })

  it('limits one address across many emails, before bcrypt', async () => {
    const { ip } = fresh()
    const d = deps('nobody@example.test')
    for (let i = 0; i < SIGN_IN_LIMITS.perAddress.limit; i++) {
      await authorizePassword({ email: fresh().email, password: 'x' }, request(ip), d)
    }
    const calls = d.compare.mock.calls.length
    await expect(authorizePassword({ email: fresh().email, password: 'x' }, request(ip), d)).rejects.toBeInstanceOf(
      TooManySignInAttempts,
    )
    expect(d.compare.mock.calls.length).toBe(calls)
  })

  it('lets the right password in again once the window has passed', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-21T10:00:00Z'))
    const { email, ip } = fresh()
    const d = deps(email)
    for (let i = 0; i < SIGN_IN_LIMITS.perEmail.limit; i++) {
      await authorizePassword({ email, password: 'wrong' }, request(ip), d)
    }
    await expect(authorizePassword({ email, password: PASSWORD }, request(ip), d)).rejects.toBeInstanceOf(
      TooManySignInAttempts,
    )
    vi.setSystemTime(new Date(Date.now() + SIGN_IN_LIMITS.perEmail.windowMs + 1000))
    expect(await authorizePassword({ email, password: PASSWORD }, request(ip), d)).toMatchObject({ email })
  })

  it('forgets earlier failures after a successful sign-in', async () => {
    const { email } = fresh()
    const d = deps(email)
    for (let i = 0; i < SIGN_IN_LIMITS.perEmail.limit - 1; i++) {
      await authorizePassword({ email, password: 'wrong' }, request(fresh().ip), d)
    }
    expect(await authorizePassword({ email, password: PASSWORD }, request(fresh().ip), d)).toMatchObject({ email })
    // A typo after a good sign-in starts from zero, not from four.
    expect(await authorizePassword({ email, password: 'wrong' }, request(fresh().ip), d)).toBeNull()
    expect(await authorizePassword({ email, password: PASSWORD }, request(fresh().ip), d)).toMatchObject({ email })
  })

  it('rejects malformed input without touching the limiter or bcrypt', async () => {
    const d = deps('a@example.test')
    expect(await authorizePassword({ email: 'not-an-email', password: '' }, request(fresh().ip), d)).toBeNull()
    expect(d.compare).not.toHaveBeenCalled()
  })

  it('reports the limit with the rate_limited code the sign-in form understands', () => {
    expect(new TooManySignInAttempts().code).toBe('rate_limited')
  })
})
