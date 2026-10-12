import { describe, expect, it } from 'vitest'
import { clientKey, rateLimit } from './rate-limit'

function req(headers: Record<string, string>): Request {
  return new Request('http://localhost/api', { headers })
}

describe('clientKey', () => {
  it('prefers X-Real-IP over the first X-Forwarded-For entry', () => {
    const r = req({ 'x-real-ip': '10.0.0.7', 'x-forwarded-for': '1.1.1.1, 10.0.0.7' })
    expect(clientKey(r, 'register')).toBe('register:10.0.0.7')
  })

  it('uses the last X-Forwarded-For entry when X-Real-IP is absent', () => {
    const r = req({ 'x-forwarded-for': '1.1.1.1, 2.2.2.2, 10.0.0.7' })
    expect(clientKey(r, 'register')).toBe('register:10.0.0.7')
  })

  it('falls back to unknown without proxy headers', () => {
    expect(clientKey(req({}), 'register')).toBe('register:unknown')
  })
})

describe('rateLimit with a client-chosen X-Forwarded-For', () => {
  it('keeps spoofed XFF values in one bucket when X-Real-IP is the same', () => {
    let allowed = 0
    for (let i = 0; i < 5; i++) {
      const r = req({
        'x-real-ip': '10.0.0.7',
        'x-forwarded-for': `1.1.1.${i}`,
      })
      if (rateLimit(clientKey(r, 'register'), 5, 60_000).ok) allowed++
    }
    expect(allowed).toBe(5)
    const again = rateLimit(clientKey(req({ 'x-real-ip': '10.0.0.7' }), 'register'), 5, 60_000)
    expect(again.ok).toBe(false)
  })
})