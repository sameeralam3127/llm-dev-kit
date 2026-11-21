import { PrismaAdapter } from '@auth/prisma-adapter'
import bcrypt from 'bcryptjs'
import NextAuth, { customFetch, type NextAuthConfig } from 'next-auth'
import Credentials from 'next-auth/providers/credentials'
import GitHub from 'next-auth/providers/github'
import Keycloak from 'next-auth/providers/keycloak'

import { authConfig } from '@/lib/auth/config'
import { rewritingFetch } from '@/lib/auth/rewriting-fetch'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import { ensureAdmin } from '@/server/identity/admin'
import { authorizePassword } from '@/server/identity/password-sign-in'
import { allowSignIn } from '@/server/identity/registration'

const BCRYPT_ROUNDS = 12

/**
 * Compared against when no user row exists, so a wrong email and a wrong
 * password take the same amount of time and the endpoint does not leak which
 * addresses are registered.
 */
const DUMMY_HASH = '$2a$12$M4d1x8Vd4bYvUq1JzPPPyeaJXwqQ0oR4YyU2vD4xNQZbkOJ4ktYAe'

export async function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, BCRYPT_ROUNDS)
}

function buildProviders(): NextAuthConfig['providers'] {
  const env = getEnv()
  const providers: NextAuthConfig['providers'] = [
    Credentials({
      id: 'credentials',
      name: 'Email and password',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      // Limited per address and per email before bcrypt runs; see
      // server/identity/password-sign-in.ts.
      authorize(raw, request) {
        return authorizePassword(raw, request, {
          findUser: (email) => db.user.findUnique({ where: { email } }),
          compare: (plain, hash) => bcrypt.compare(plain, hash),
          dummyHash: DUMMY_HASH,
        })
      },
    }),
  ]

  if (env.AUTH_GITHUB_ID && env.AUTH_GITHUB_SECRET) {
    providers.push(
      // No allowDangerousEmailAccountLinking: whoever controls a GitHub
      // account with a matching email would otherwise take over the local
      // account. A clash now fails with OAuthAccountNotLinked.
      GitHub({
        clientId: env.AUTH_GITHUB_ID,
        clientSecret: env.AUTH_GITHUB_SECRET,
      }),
    )
  }

  if (ssoConfigured()) {
    const issuer = env.AUTH_KEYCLOAK_ISSUER!.replace(/\/$/, '')
    const internal = env.AUTH_KEYCLOAK_INTERNAL_ISSUER?.replace(/\/$/, '')
    providers.push(
      Keycloak({
        clientId: env.AUTH_KEYCLOAK_ID!,
        clientSecret: env.AUTH_KEYCLOAK_SECRET!,
        issuer,
        // The browser and the tokens use the public issuer URL; this server
        // fetches discovery, tokens and keys through the internal one.
        ...(internal && internal !== issuer
          ? { [customFetch]: rewritingFetch(issuer, internal) }
          : {}),
      }),
    )
  }

  return providers
}

function ssoConfigured(): boolean {
  const env = getEnv()
  return Boolean(env.AUTH_KEYCLOAK_ID && env.AUTH_KEYCLOAK_SECRET && env.AUTH_KEYCLOAK_ISSUER)
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PrismaAdapter(db),
  providers: buildProviders(),
  callbacks: {
    ...authConfig.callbacks,
    // Runs before the adapter creates a user: with registration closed, a
    // first GitHub or SSO sign-in must not open an account.
    signIn: ({ account, user }) => allowSignIn(account, user.email),
  },
  events: {
    // An OAuth sign-in can create the very first user.
    async createUser() {
      await ensureAdmin()
    },
  },
  secret: process.env.AUTH_SECRET,
})

/** Which external sign-in buttons the UI should offer. */
export function oauthProvidersEnabled(): { github: boolean; sso: boolean } {
  const env = getEnv()
  return {
    github: Boolean(env.AUTH_GITHUB_ID && env.AUTH_GITHUB_SECRET),
    sso: ssoConfigured(),
  }
}
