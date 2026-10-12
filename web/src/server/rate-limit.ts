import 'server-only'

interface Bucket {
  count: number
  resetAt: number
}

const buckets = new Map<string, Bucket>()
let lastSweep = 0

/**
 * Fixed-window limiter held in process memory.
 *
 * Deliberately simple: it exists to blunt credential stuffing and runaway
 * clients on a single-instance deployment. Behind more than one replica this
 * becomes per-replica — swap in Redis (the compose stack already runs one)
 * before relying on it as a hard quota.
 */
export function rateLimit(
  key: string,
  limit: number,
  windowMs: number,
): { ok: boolean; remaining: number; retryAfterSeconds: number } {
  const now = Date.now()

  // Amortised cleanup so abandoned keys cannot grow the map without bound.
  if (now - lastSweep > 60_000) {
    for (const [bucketKey, bucket] of buckets) {
      if (bucket.resetAt <= now) buckets.delete(bucketKey)
    }
    lastSweep = now
  }

  const existing = buckets.get(key)
  if (!existing || existing.resetAt <= now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs })
    return { ok: true, remaining: limit - 1, retryAfterSeconds: 0 }
  }

  existing.count += 1
  const ok = existing.count <= limit

  return {
    ok,
    remaining: Math.max(0, limit - existing.count),
    retryAfterSeconds: ok ? 0 : Math.ceil((existing.resetAt - now) / 1000),
  }
}

/** Best-effort client identity for anonymous endpoints. */
export function clientKey(request: Request, scope: string): string {
  // X-Real-IP is set by the gateway from $remote_addr, which a client cannot
  // override. X-Forwarded-For's first entry is client-chosen: the gateway
  // appends the real address, so trusting the first entry would let a client
  // get a fresh rate-limit bucket on every request by rotating the header.
  const real = request.headers.get('x-real-ip')?.trim()
  if (real) return `${scope}:${real}`
  // Without X-Real-IP, use the last X-Forwarded-For entry: the one the
  // nearest trusted proxy appended.
  const forwarded = request.headers.get('x-forwarded-for')
  const ip =
    forwarded?.split(',').map((entry) => entry.trim()).filter(Boolean).pop() ||
    'unknown'
  return `${scope}:${ip}`
}