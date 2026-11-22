// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { coreRole, resetWorkspaceCache, teamWorkspaceId } from './workspaces'

const BASE = 'http://core-api.test:8030'
const SERVICE = 'web-service-token-0123456789-0123456789'

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

// core-api's real shape: every response is wrapped as {"data": ...}.
const synced = (workspaceId: string, role: string | null) => ({
  status: 200,
  body: { data: { workspace_id: workspaceId, role } },
})

const options = (fetch: typeof globalThis.fetch) => ({ baseUrl: BASE, serviceToken: SERVICE, fetch })

beforeEach(() => resetWorkspaceCache())

describe('team workspace', () => {
  it('maps web roles onto core-api roles', () => {
    expect(coreRole('admin')).toBe('owner')
    expect(coreRole('user')).toBe('editor')
    expect(coreRole('viewer')).toBe('reader')
    expect(coreRole('something-else')).toBe('reader')
  })

  it('syncs the user\'s role with the web app\'s service token and returns the workspace', async () => {
    const core = fakeCore([synced('ws-team', 'editor')])
    expect(await teamWorkspaceId('cm0user', 'user', options(core.fetch))).toBe('ws-team')
    expect(core.calls).toEqual([
      {
        method: 'PUT',
        url: `${BASE}/api/v1/internal/team-members/cm0user`,
        auth: `Bearer ${SERVICE}`,
        body: { role: 'editor' },
      },
    ])
  })

  it('is remembered per role, so a chat turn costs no extra call', async () => {
    const core = fakeCore([synced('ws-team', 'editor')])
    await teamWorkspaceId('u1', 'user', options(core.fetch))
    expect(await teamWorkspaceId('u1', 'user', options(core.fetch))).toBe('ws-team')
    expect(core.calls).toHaveLength(1)
  })

  it('re-syncs after a role change in the admin console', async () => {
    const core = fakeCore([synced('ws-team', 'editor'), synced('ws-team', 'owner')])
    await teamWorkspaceId('u1', 'user', options(core.fetch))
    await teamWorkspaceId('u1', 'admin', options(core.fetch))
    expect(core.calls.map((c) => c.body)).toEqual([{ role: 'editor' }, { role: 'owner' }])
  })

  it('reports core-api being unavailable or refusing as an upstream failure', async () => {
    for (const status of [401, 503]) {
      resetWorkspaceCache()
      const core = fakeCore([{ status, body: { error: { code: 'x' } } }])
      await expect(teamWorkspaceId('u1', 'user', options(core.fetch))).rejects.toMatchObject({
        code: 'upstream_error',
      })
    }
  })

  it('treats an answer in an unexpected shape as an upstream failure', async () => {
    const core = fakeCore([{ status: 200, body: { workspace_id: 'ws' } }])
    await expect(teamWorkspaceId('u1', 'user', options(core.fetch))).rejects.toMatchObject({
      code: 'upstream_error',
    })
  })
})
