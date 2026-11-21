import { ROUTES } from '@/lib/constants'
import { db } from '@/lib/db'
import { getEnv, type ServerEnv } from '@/lib/env'

/** The `?error=` code the sign-in page explains when a sign-up is refused. */
export const REGISTRATION_CLOSED = 'RegistrationClosed'

/** The Auth.js provider id of the bundled single sign-on (Keycloak). */
const SSO_PROVIDER = 'keycloak'

type RegistrationEnv = Pick<ServerEnv, 'ALLOW_REGISTRATION' | 'AUTH_SSO_CREATE_USERS'>

/**
 * Whether a first sign-in through `provider` may create a user.
 *
 * `ALLOW_REGISTRATION` covers every way in: password, GitHub and SSO. Single
 * sign-on is the one exception an operator can opt into, because its users are
 * already vetted by the identity provider: `AUTH_SSO_CREATE_USERS=true`.
 */
export function mayCreateUser(provider: string, env: RegistrationEnv): boolean {
  if (env.ALLOW_REGISTRATION) return true
  return provider === SSO_PROVIDER && env.AUTH_SSO_CREATE_USERS
}

interface SignInAccount {
  type: string
  provider: string
  providerAccountId: string
}

/**
 * The Auth.js `signIn` callback. It runs before the adapter creates a user, so
 * refusing here is what stops an OAuth or SSO sign-in from opening an account
 * while registration is closed. Returns `true` to continue, or the sign-in
 * page with a reason.
 */
export async function allowSignIn(
  account: SignInAccount | null | undefined,
  email: string | null | undefined,
): Promise<true | string> {
  // Password sign-in never creates a user; sign-up has its own route and check.
  if (!account || account.type === 'credentials') return true

  const env = getEnv()
  if (env.ALLOW_REGISTRATION) return true

  const linked = await db.account.findUnique({
    where: {
      provider_providerAccountId: {
        provider: account.provider,
        providerAccountId: account.providerAccountId,
      },
    },
    select: { id: true },
  })
  if (linked) return true

  // An existing user with this email but no linked account: Auth.js does not
  // link by email, so it creates nothing and refuses with the clearer
  // OAuthAccountNotLinked message. Let it.
  if (email && (await db.user.findUnique({ where: { email }, select: { id: true } }))) {
    return true
  }

  if (mayCreateUser(account.provider, env)) return true
  return `${ROUTES.login}?error=${REGISTRATION_CLOSED}`
}
