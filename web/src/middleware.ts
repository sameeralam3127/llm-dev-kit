import NextAuth from 'next-auth'
import { NextResponse } from 'next/server'

import { authConfig } from '@/lib/auth/config'
import { ROUTES } from '@/lib/constants'

const { auth } = NextAuth(authConfig)

/** Reachable without a session. Everything else requires one. */
const PUBLIC_PREFIXES = ['/login', '/register', '/share', '/api/auth']

export default auth((request) => {
  const { pathname, search } = request.nextUrl
  const isAuthenticated = Boolean(request.auth?.user)
  const isPublic = PUBLIC_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )

  // Signed-in users have no business on the sign-in screens.
  if (isAuthenticated && (pathname === ROUTES.login || pathname === ROUTES.register)) {
    return NextResponse.redirect(new URL(ROUTES.home, request.nextUrl))
  }

  if (isAuthenticated || isPublic) return NextResponse.next()

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
})

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)'],
}
