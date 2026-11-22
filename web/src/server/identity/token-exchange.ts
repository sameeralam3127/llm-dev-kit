import { rateLimit } from '@/server/rate-limit'

/**
 * Failed exchanges allowed per caller address. Only failures count: the
 * Python services all reach this route from one address, so a limit on
 * attempts would let anyone sending made-up keys lock out every real key.
 * Lookups are a SHA-256 and an indexed read, cheap enough to do first.
 */
export const TOKEN_EXCHANGE_FAILURES = { limit: 60, windowMs: 60_000 } as const

export type ApiKeyCheck =
  | { ok: true; userId: string }
  | { ok: false; reason: 'invalid' }
  | { ok: false; reason: 'rate_limited'; retryAfterSeconds: number }

/** Resolve `key`, charging `source`'s failure limit only when it is invalid. */
export async function checkApiKey(
  key: string,
  source: string,
  resolve: (key: string) => Promise<string | null>,
): Promise<ApiKeyCheck> {
  const userId = key ? await resolve(key) : null
  if (userId) return { ok: true, userId }

  const { limit, windowMs } = TOKEN_EXCHANGE_FAILURES
  const failures = rateLimit(`token-exchange-failures:${source}`, limit, windowMs)
  if (!failures.ok) {
    return { ok: false, reason: 'rate_limited', retryAfterSeconds: failures.retryAfterSeconds }
  }
  return { ok: false, reason: 'invalid' }
}
