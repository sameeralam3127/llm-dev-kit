import 'server-only'

import { getEnv } from '@/lib/env'
import { OpenAICompatibleProvider } from '@/lib/llm/openai-compatible'
import type { ChatProvider, ProviderModel } from '@/lib/llm/types'
import { personalWorkspaceId } from '@/server/core-api/workspaces'
import { mintAccessToken } from '@/server/identity/tokens'

let provider: ChatProvider | null = null

/** The single place the app decides which backend generates tokens. */
export function getChatProvider(): ChatProvider {
  if (!provider) {
    const env = getEnv()
    provider = new OpenAICompatibleProvider({
      baseUrl: backendBaseUrl(),
      ...(env.LLM_API_KEY ? { apiKey: env.LLM_API_KEY } : {}),
      timeoutMs: env.LLM_REQUEST_TIMEOUT_MS,
    })
  }
  return provider
}

/** core-api's `/v1` when CORE_API_URL is set (the lite profile), else LLM_BASE_URL. */
export function backendBaseUrl(): string {
  const env = getEnv()
  return env.CORE_API_URL ? `${env.CORE_API_URL.replace(/\/$/, '')}/v1` : env.LLM_BASE_URL
}

export interface BackendOptions {
  authorization?: string
  workspaceId?: string
}

/**
 * How to call the model backend on `userId`'s behalf: with their own
 * short-lived access token, so the services see who is asking. core-api also
 * needs the workspace to act in: the user's personal one. A configured
 * third-party key replaces the token.
 */
export async function backendOptions(userId: string): Promise<BackendOptions> {
  const env = getEnv()
  if (env.CORE_API_URL) {
    const { token } = await mintAccessToken(userId)
    const baseUrl = env.CORE_API_URL.replace(/\/$/, '')
    return { authorization: token, workspaceId: await personalWorkspaceId(userId, token, { baseUrl }) }
  }
  if (env.LLM_API_KEY) return {}
  return { authorization: (await mintAccessToken(userId)).token }
}

const MODEL_CACHE_TTL_MS = 60_000
let modelCache: { models: ProviderModel[]; expiresAt: number } | null = null

/**
 * The model list is small, changes rarely, and is requested on every page load.
 * A short TTL keeps the sidebar responsive without going stale after a pull.
 */
export async function getAvailableModels(userId: string): Promise<ProviderModel[]> {
  const now = Date.now()
  if (modelCache && modelCache.expiresAt > now) return modelCache.models

  const env = getEnv()
  try {
    const models = await getChatProvider().listModels(await backendOptions(userId))
    const resolved =
      models.length > 0 ? models : [fallbackModel(env.DEFAULT_MODEL)]
    modelCache = { models: resolved, expiresAt: now + MODEL_CACHE_TTL_MS }
    return resolved
  } catch {
    // Never block the UI on a model-list failure — the configured default is
    // still worth offering, and the send path reports its own errors.
    return [fallbackModel(env.DEFAULT_MODEL)]
  }
}

export function invalidateModelCache(): void {
  modelCache = null
}

function fallbackModel(id: string): ProviderModel {
  return { id, label: id, provider: 'local' }
}

export type { ChatProvider, ProviderModel } from '@/lib/llm/types'
export { ProviderError } from '@/lib/llm/types'
