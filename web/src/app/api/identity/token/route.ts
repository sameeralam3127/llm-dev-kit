import { NextResponse } from 'next/server'

import { resolveApiKey } from '@/server/identity/api-keys'
import { mintAccessToken } from '@/server/identity/tokens'
import { clientKey, RATE_LIMITS, rateLimit } from '@/server/rate-limit'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

function unauthorized() {
  return NextResponse.json(
    { error: { code: 'unauthorized', message: 'Invalid API key' } },
    { status: 401, headers: { 'WWW-Authenticate': 'Bearer realm="llm-dev-kit"' } },
  )
}

/**
 * Exchange a personal API key for a short-lived access token.
 *
 * The Python services call this when a request arrives with `sk-ldk-...` and
 * cache the result for a minute, so it sees roughly one call per key per
 * minute per service, not one per request.
 */
export async function POST(request: Request) {
  const limit = rateLimit(
    clientKey(request, 'token-exchange'),
    RATE_LIMITS.tokenExchange.limit,
    RATE_LIMITS.tokenExchange.windowMs,
  )
  if (!limit.ok) {
    return NextResponse.json(
      { error: { code: 'rate_limited', message: 'Too many token requests' } },
      { status: 429, headers: { 'Retry-After': String(limit.retryAfterSeconds) } },
    )
  }

  const header = request.headers.get('authorization') ?? ''
  const key = header.toLowerCase().startsWith('bearer ') ? header.slice(7).trim() : ''
  const userId = key ? await resolveApiKey(key) : null
  if (!userId) return unauthorized()

  const { token, expiresIn } = await mintAccessToken(userId, 'api_key')
  return NextResponse.json(
    { access_token: token, token_type: 'Bearer', expires_in: expiresIn },
    { headers: { 'Cache-Control': 'no-store' } },
  )
}
