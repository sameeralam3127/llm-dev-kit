import { PrismaAdapter } from '@auth/prisma-adapter'
import bcrypt from 'bcryptjs'
import NextAuth, { type NextAuthConfig } from 'next-auth'
import Credentials from 'next-auth/providers/credentials'
import GitHub from 'next-auth/providers/github'

import { authConfig } from '@/lib/auth/config'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import { loginSchema } from '@/lib/validations/auth'

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
      async authorize(raw) {
        const parsed = loginSchema.safeParse(raw)
        if (!parsed.success) return null

        const { email, password } = parsed.data
        const user = await db.user.findUnique({ where: { email } })

        const matches = await bcrypt.compare(
          password,
          user?.passwordHash ?? DUMMY_HASH,
        )
        if (!user?.passwordHash || !matches) return null

        return {
          id: user.id,
          name: user.name,
          email: user.email,
          image: user.image,
        }
      },
    }),
  ]

  if (env.AUTH_GITHUB_ID && env.AUTH_GITHUB_SECRET) {
    providers.push(
      GitHub({
        clientId: env.AUTH_GITHUB_ID,
        clientSecret: env.AUTH_GITHUB_SECRET,
        allowDangerousEmailAccountLinking: true,
      }),
    )
  }

  return providers
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PrismaAdapter(db),
  providers: buildProviders(),
  secret: process.env.AUTH_SECRET,
})

/** True when GitHub sign-in should be offered in the UI. */
export function oauthProvidersEnabled(): { github: boolean } {
  const env = getEnv()
  return { github: Boolean(env.AUTH_GITHUB_ID && env.AUTH_GITHUB_SECRET) }
}
