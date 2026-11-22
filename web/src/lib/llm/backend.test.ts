// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

const env = vi.hoisted(() => ({ value: {} as Record<string, unknown> }))
vi.mock('server-only', () => ({}))
vi.mock('@/lib/env', () => ({ getEnv: () => env.value }))
vi.mock('@/lib/db', () => ({
  db: { user: { findUnique: vi.fn(async () => ({ role: 'user' })) } },
}))
vi.mock('@/server/identity/tokens', () => ({
  mintAccessToken: vi.fn(async (userId: string) => ({ token: `token-for-${userId}`, expiresIn: 300 })),
}))
const workspaces = vi.hoisted(() => ({ teamWorkspaceId: vi.fn(async () => 'ws-team') }))
vi.mock('@/server/core-api/workspaces', () => workspaces)

import { backendBaseUrl, backendOptions } from './index'

const BASE = { LLM_BASE_URL: 'http://rag.test/v1', LLM_REQUEST_TIMEOUT_MS: 5000, DEFAULT_MODEL: 'm' }
const SERVICE = 'web-service-token-0123456789-0123456789'

beforeEach(() => workspaces.teamWorkspaceId.mockClear())

describe('which backend the web app calls', () => {
  it('is rag-service with the user\'s token by default, as before', async () => {
    env.value = { ...BASE }
    expect(backendBaseUrl()).toBe('http://rag.test/v1')
    expect(await backendOptions('u1')).toEqual({ authorization: 'token-for-u1' })
    expect(workspaces.teamWorkspaceId).not.toHaveBeenCalled()
  })

  it('is a third-party backend with its own key when LLM_API_KEY is set', async () => {
    env.value = { ...BASE, LLM_API_KEY: 'sk-real' }
    expect(await backendOptions('u1')).toEqual({})
  })

  it('is core-api, in the shared team workspace with the user\'s role, when CORE_API_URL is set', async () => {
    env.value = { ...BASE, CORE_API_URL: 'http://core-api:8030/', WEB_SERVICE_TOKEN: SERVICE }
    expect(backendBaseUrl()).toBe('http://core-api:8030/v1')
    expect(await backendOptions('u1')).toEqual({ authorization: 'token-for-u1', workspaceId: 'ws-team' })
    expect(workspaces.teamWorkspaceId).toHaveBeenCalledWith('u1', 'user', {
      baseUrl: 'http://core-api:8030',
      serviceToken: SERVICE,
    })
  })

  it('refuses to guess when core-api is set but the web app has no service token', async () => {
    env.value = { ...BASE, CORE_API_URL: 'http://core-api:8030' }
    await expect(backendOptions('u1')).rejects.toMatchObject({ code: 'upstream_error' })
  })
})
