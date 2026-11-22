// @vitest-environment node
import { describe, expect, it } from 'vitest'

import { contentSecurityPolicy, newNonce } from './csp'

const directives = (policy: string) =>
  Object.fromEntries(
    policy.split(';').map((part) => {
      const [name, ...values] = part.trim().split(/\s+/)
      return [name, values]
    }),
  )

describe('content security policy', () => {
  it('allows only scripts carrying this response nonce', () => {
    const policy = directives(contentSecurityPolicy('abc123'))
    expect(policy['script-src']).toEqual(["'nonce-abc123'", "'strict-dynamic'"])
    expect(policy['script-src']).not.toContain("'unsafe-inline'")
    expect(policy['script-src']).not.toContain("'unsafe-eval'")
  })

  it('refuses framing, plugins, foreign forms and base rewrites', () => {
    const policy = directives(contentSecurityPolicy('n'))
    expect(policy['frame-ancestors']).toEqual(["'none'"])
    expect(policy['object-src']).toEqual(["'none'"])
    expect(policy['form-action']).toEqual(["'self'"])
    expect(policy['base-uri']).toEqual(["'self'"])
    expect(policy['default-src']).toEqual(["'self'"])
  })

  it('loads images only from this app and GitHub avatars, so model output cannot beacon out', () => {
    const images = directives(contentSecurityPolicy('n'))['img-src']
    expect(images).toEqual(["'self'", 'data:', 'blob:', 'https://avatars.githubusercontent.com'])
    expect(images).not.toContain('https:')
    expect(images).not.toContain('*')
  })

  it('relaxes only what the dev server needs, only in development', () => {
    const dev = directives(contentSecurityPolicy('n', { dev: true }))
    expect(dev['script-src']).toContain("'unsafe-eval'")
    expect(dev['connect-src']).toContain('ws:')
    expect(directives(contentSecurityPolicy('n'))['connect-src']).toEqual(["'self'"])
  })

  it('makes a fresh, unguessable nonce each time', () => {
    const a = newNonce()
    expect(a).toMatch(/^[A-Za-z0-9+/=]{24,}$/)
    expect(newNonce()).not.toBe(a)
  })
})
