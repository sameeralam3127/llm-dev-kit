import type { NextAuthConfig } from 'next-auth'

import { ROUTES } from '@/lib/constants'

/**
 * Edge-safe half of the auth setup: no Prisma, no bcrypt, no Node built-ins.
 * `middleware.ts` imports only this, which keeps it deployable to the edge
 * runtime; the full config in `./index.ts` extends it with the adapter and the
 * credentials provider.
 */
export const authConfig = {
  trustHost: true,
  session: { strategy: 'jwt', maxAge: 30 * 24 * 60 * 60 },
  pages: {
    signIn: ROUTES.login,
    error: ROUTES.login,
  },
  providers: [],
  callbacks: {
    jwt({ token, user }) {
      if (user) {
        token.id = user.id ?? token.sub ?? ''
        token.picture = user.image ?? null
      }
      return token
    },
    session({ session, token }) {
      if (session.user) {
        session.user.id = (token.id as string | undefined) ?? token.sub ?? ''
      }
      return session
    },
    authorized({ auth }) {
      return Boolean(auth?.user)
    },
  },
} satisfies NextAuthConfig
