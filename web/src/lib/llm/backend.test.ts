// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

const env = vi.hoisted(() => ({ value: {} as Record<string, unknown> }))
vi.mock('server-only', () => ({}))
vi.mock('@/lib/env', () => ({ getEnv: () => env.value }))
vi.mock('@/server/identity/tokens', () => ({
  mintAccessToken: vi.fn(async (userId: string) => ({ token: `token-for-${userId}`, expiresIn: 300 })),
}))
const workspaces = vi.hoisted(() => ({ personalWorkspaceId: vi.fn(async () => 'ws-personal') }))
vi.mock('@/server/core-api/workspaces', () => workspaces)

import { backendOptions, backendBaseUrl } from './index'

const BASE = { LLM_BASE_URL: 'http://rag.test/v1', LLM_REQUEST_TIMEOUT_MS: 5000, DEFAULT_MODEL: 'm' }

beforeEach(() => workspaces.personalWorkspaceId.mockClear())

describe('which backend the web app calls', () => {
  it('is rag-service with the user\'s token by default, as before', async () => {
    env.value = { ...BASE }
    expect(backendBaseUrl()).toBe('http://rag.test/v1')
    expect(await backendOptions('u1')).toEqual({ authorization: 'token-for-u1' })
    expect(workspaces.personalWorkspaceId).not.toHaveBeenCalled()
  })

  it('is a third-party backend with its own key when LLM_API_KEY is set', async () => {
    env.value = { ...BASE, LLM_API_KEY: 'sk-real' }
    expect(await backendOptions('u1')).toEqual({})
  })

  it('is core-api, in the user\'s personal workspace, when CORE_API_URL is set', async () => {
    env.value = { ...BASE, CORE_API_URL: 'http://core-api:8030/' }
    expect(backendBaseUrl()).toBe('http://core-api:8030/v1')
    expect(await backendOptions('u1')).toEqual({ authorization: 'token-for-u1', workspaceId: 'ws-personal' })
    expect(workspaces.personalWorkspaceId).toHaveBeenCalledWith('u1', 'token-for-u1', {
      baseUrl: 'http://core-api:8030',
    })
  })
})
