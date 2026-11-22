import NextAuth from 'next-auth'
import { type NextRequest, NextResponse } from 'next/server'

import { authConfig } from '@/lib/auth/config'
import { ROUTES } from '@/lib/constants'
import { contentSecurityPolicy, newNonce } from '@/lib/security/csp'

const { auth } = NextAuth(authConfig)

/**
 * Reachable without a session. Everything else requires one. The identity
 * endpoints authenticate their own callers: the JWKS is public by design and
 * the token exchange takes an API key, not a session.
 */
const PUBLIC_PREFIXES = [
  '/login',
  '/register',
  '/share',
  '/api/auth',
  '/.well-known',
  '/api/identity',
]

/**
 * Pass the request on with its CSP. Next.js reads the nonce from the request's
 * Content-Security-Policy header and puts it on its own scripts; the root
 * layout reads `x-nonce` for the theme script.
 */
function next(request: NextRequest, nonce: string, csp: string) {
  const headers = new Headers(request.headers)
  headers.set('x-nonce', nonce)
  headers.set('Content-Security-Policy', csp)
  return NextResponse.next({ request: { headers } })
}

function route(request: NextRequest & { auth: unknown }, nonce: string, csp: string) {
  const { pathname, search } = request.nextUrl
  const isAuthenticated = Boolean((request.auth as { user?: unknown } | null)?.user)
  const isPublic = PUBLIC_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )

  // Signed-in users have no business on the sign-in screens.
  if (isAuthenticated && (pathname === ROUTES.login || pathname === ROUTES.register)) {
    return NextResponse.redirect(new URL(ROUTES.home, request.nextUrl))
  }

  if (isAuthenticated || isPublic) return next(request, nonce, csp)

  // API callers get a machine-readable 401 rather than an HTML redirect they
  // would have to sniff for.
  if (pathname.startsWith('/api/')) {
    return NextResponse.json(
      { error: { code: 'unauthorized', message: 'Sign in to continue' } },
      { status: 401 },
    )
  }

  const loginUrl = new URL(ROUTES.login, request.nextUrl)
  if (pathname !== ROUTES.home) {
    loginUrl.searchParams.set('callbackUrl', `${pathname}${search}`)
  }
  return NextResponse.redirect(loginUrl)
}

export default auth((request) => {
  const nonce = newNonce()
  const csp = contentSecurityPolicy(nonce, { dev: process.env.NODE_ENV === 'development' })
  const response = route(request, nonce, csp)
  response.headers.set('Content-Security-Policy', csp)
  return response
})

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)'],
}
