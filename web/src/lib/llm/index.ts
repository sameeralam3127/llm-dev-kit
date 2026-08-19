import 'server-only'

import { getEnv } from '@/lib/env'
import { OpenAICompatibleProvider } from '@/lib/llm/openai-compatible'
import type { ChatProvider, ProviderModel } from '@/lib/llm/types'

let provider: ChatProvider | null = null

/** The single place the app decides which backend generates tokens. */
export function getChatProvider(): ChatProvider {
  if (!provider) {
    const env = getEnv()
    provider = new OpenAICompatibleProvider({
      baseUrl: env.LLM_BASE_URL,
      apiKey: env.LLM_API_KEY,
      timeoutMs: env.LLM_REQUEST_TIMEOUT_MS,
    })
  }
  return provider
}

const MODEL_CACHE_TTL_MS = 60_000
let modelCache: { models: ProviderModel[]; expiresAt: number } | null = null

/**
 * The model list is small, changes rarely, and is requested on every page load.
 * A short TTL keeps the sidebar responsive without going stale after a pull.
 */
export async function getAvailableModels(): Promise<ProviderModel[]> {
  const now = Date.now()
  if (modelCache && modelCache.expiresAt > now) return modelCache.models

  const env = getEnv()
  try {
    const models = await getChatProvider().listModels()
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
