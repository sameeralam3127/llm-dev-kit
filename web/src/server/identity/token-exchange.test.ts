// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'

import { checkApiKey, TOKEN_EXCHANGE_FAILURES } from './token-exchange'

const VALID = 'sk-ldk-valid'
const resolve = vi.fn(async (key: string) => (key === VALID ? 'u1' : null))

let sources = 0
/** A fresh caller address, so tests never share a limiter bucket. */
const source = () => `token-exchange:10.93.0.${++sources}`

describe('token exchange', () => {
  it('lets a valid key through after a flood of invalid ones from the same caller', async () => {
    const caller = source()
    for (let i = 0; i < 301; i++) await checkApiKey(`sk-ldk-guess-${i}`, caller, resolve)

    expect(await checkApiKey(VALID, caller, resolve)).toEqual({ ok: true, userId: 'u1' })
  })

  it('never charges the limit for a valid key', async () => {
    const caller = source()
    for (let i = 0; i < 500; i++) {
      expect(await checkApiKey(VALID, caller, resolve)).toEqual({ ok: true, userId: 'u1' })
    }
    expect(await checkApiKey('sk-ldk-wrong', caller, resolve)).toEqual({ ok: false, reason: 'invalid' })
  })

  it('throttles repeated failures from one caller, with a retry time', async () => {
    const caller = source()
    for (let i = 0; i < TOKEN_EXCHANGE_FAILURES.limit; i++) {
      expect(await checkApiKey(`sk-ldk-guess-${i}`, caller, resolve)).toEqual({ ok: false, reason: 'invalid' })
    }

    const refused = await checkApiKey('sk-ldk-one-more', caller, resolve)
    expect(refused).toMatchObject({ ok: false, reason: 'rate_limited' })
    expect(refused.ok === false && refused.reason === 'rate_limited' && refused.retryAfterSeconds).toBeGreaterThan(0)

    expect(await checkApiKey('sk-ldk-guess', source(), resolve)).toEqual({ ok: false, reason: 'invalid' })
  })

  it('treats a missing key as a failure without looking it up', async () => {
    resolve.mockClear()
    expect(await checkApiKey('', source(), resolve)).toEqual({ ok: false, reason: 'invalid' })
    expect(resolve).not.toHaveBeenCalled()
  })
})
