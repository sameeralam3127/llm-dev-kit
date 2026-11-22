// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { personalSlug, personalWorkspaceId, resetWorkspaceCache } from './workspaces'

const BASE = 'http://core-api.test:8030'

interface Call {
  method: string
  url: string
  auth: string | null
  body: unknown
}

function fakeCore(responses: Array<{ status: number; body: unknown }>) {
  const calls: Call[] = []
  const fetch = vi.fn(async (url: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers)
    calls.push({
      method: init.method ?? 'GET',
      url,
      auth: headers.get('authorization'),
      body: init.body ? JSON.parse(String(init.body)) : undefined,
    })
    const next = responses.shift()
    if (!next) throw new Error(`unexpected call ${init.method} ${url}`)
    return new Response(JSON.stringify(next.body), { status: next.status })
  })
  return { fetch: fetch as unknown as typeof globalThis.fetch, calls }
}

// core-api's real shapes: every response is wrapped as {"data": ...}.
const listing = (...workspaces: Array<{ id: string; slug: string }>) => ({
  status: 200,
  body: { data: workspaces.map((w) => ({ ...w, name: 'x', role: 'owner' })) },
})

beforeEach(() => resetWorkspaceCache())

describe('personal workspace', () => {
  it('has a stable slug that core-api accepts, whatever the user id looks like', () => {
    const slug = personalSlug('cm0abcDEF_123')
    expect(slug).toMatch(/^[a-z0-9][a-z0-9-]{0,62}$/)
    expect(personalSlug('cm0abcDEF_123')).toBe(slug)
    expect(personalSlug('another-user')).not.toBe(slug)
  })

  it('is found among the user\'s workspaces, with their own token', async () => {
    const core = fakeCore([listing({ id: 'ws-other', slug: 'team' }, { id: 'ws-me', slug: personalSlug('u1') })])
    expect(await personalWorkspaceId('u1', 'tok', { baseUrl: BASE, fetch: core.fetch })).toBe('ws-me')
    expect(core.calls).toEqual([{ method: 'GET', url: `${BASE}/api/v1/workspaces`, auth: 'Bearer tok', body: undefined }])
  })

  it('is created on first use', async () => {
    const core = fakeCore([listing(), { status: 201, body: { data: { id: 'ws-new', slug: personalSlug('u1') } } }])
    expect(await personalWorkspaceId('u1', 'tok', { baseUrl: BASE, fetch: core.fetch })).toBe('ws-new')
    expect(core.calls[1]).toMatchObject({
      method: 'POST',
      url: `${BASE}/api/v1/workspaces`,
      body: { slug: personalSlug('u1'), name: 'Personal' },
    })
  })

  it('survives two first uses racing: the loser reads the winner\'s workspace', async () => {
    const core = fakeCore([
      listing(),
      { status: 409, body: { error: { code: 'conflict' } } },
      listing({ id: 'ws-won', slug: personalSlug('u1') }),
    ])
    expect(await personalWorkspaceId('u1', 'tok', { baseUrl: BASE, fetch: core.fetch })).toBe('ws-won')
  })

  it('is remembered, so a chat turn costs no extra call', async () => {
    const core = fakeCore([listing({ id: 'ws-me', slug: personalSlug('u1') })])
    await personalWorkspaceId('u1', 'tok', { baseUrl: BASE, fetch: core.fetch })
    expect(await personalWorkspaceId('u1', 'tok2', { baseUrl: BASE, fetch: core.fetch })).toBe('ws-me')
    expect(core.calls).toHaveLength(1)
  })

  it('reports core-api being unavailable as an upstream failure', async () => {
    const core = fakeCore([{ status: 503, body: { error: { code: 'upstream_unavailable' } } }])
    await expect(personalWorkspaceId('u1', 'tok', { baseUrl: BASE, fetch: core.fetch })).rejects.toMatchObject({
      code: 'upstream_error',
    })
  })

  it('treats an answer in an unexpected shape as an upstream failure', async () => {
    const core = fakeCore([{ status: 200, body: { workspaces: [] } }])
    await expect(personalWorkspaceId('u1', 'tok', { baseUrl: BASE, fetch: core.fetch })).rejects.toMatchObject({
      code: 'upstream_error',
    })
  })
})
