import { NextResponse } from 'next/server'

import { resolveApiKey } from '@/server/identity/api-keys'
import { checkApiKey } from '@/server/identity/token-exchange'
import { mintAccessToken } from '@/server/identity/tokens'
import { clientKey } from '@/server/rate-limit'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/**
 * Exchange a personal API key for a short-lived access token.
 *
 * The Python services call this when a request arrives with `sk-ldk-...` and
 * cache the result for a minute, so it sees roughly one call per key per
 * minute per service, not one per request. Only invalid keys are rate
 * limited (server/identity/token-exchange.ts).
 */
export async function POST(request: Request) {
  const header = request.headers.get('authorization') ?? ''
  const key = header.toLowerCase().startsWith('bearer ') ? header.slice(7).trim() : ''

  const check = await checkApiKey(key, clientKey(request, 'token-exchange'), resolveApiKey)
  if (!check.ok && check.reason === 'rate_limited') {
    return NextResponse.json(
      { error: { code: 'rate_limited', message: 'Too many invalid API keys' } },
      { status: 429, headers: { 'Retry-After': String(check.retryAfterSeconds) } },
    )
  }
  if (!check.ok) {
    return NextResponse.json(
      { error: { code: 'unauthorized', message: 'Invalid API key' } },
      { status: 401, headers: { 'WWW-Authenticate': 'Bearer realm="llm-dev-kit"' } },
    )
  }

  const { token, expiresIn } = await mintAccessToken(check.userId, 'api_key')
  return NextResponse.json(
    { access_token: token, token_type: 'Bearer', expires_in: expiresIn },
    { headers: { 'Cache-Control': 'no-store' } },
  )
}
