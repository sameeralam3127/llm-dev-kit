import { CredentialsSignin } from 'next-auth'

import { loginSchema } from '@/lib/validations/auth'
import { clearLimit, clientKey, isLimited, RATE_LIMITS, rateLimit } from '@/server/rate-limit'

/**
 * Limits on password sign-in, both checked before bcrypt runs.
 *
 * - Per client address, every attempt counts: bcrypt at cost 12 is ~200 ms of
 *   CPU in pure JavaScript, so this is what stops one client tying up the
 *   web app for everyone.
 * - Per email, only failures count, so signing in correctly is never blocked:
 *   this is what stops guessing one account's password from many addresses,
 *   and it still works when a client can choose its own address (the app
 *   reached without the gateway). Unknown emails count the same way, so the
 *   limit reveals nothing about which accounts exist.
 *
 * Both are in-process (see rate-limit.ts): per replica, reset on restart. The
 * numbers live in RATE_LIMITS, which the admin console shows.
 */
export const SIGN_IN_LIMITS = {
  perAddress: RATE_LIMITS.signIn,
  perEmail: RATE_LIMITS.signInFailures,
} as const

/** Thrown when a limit is hit; the sign-in form shows its `code`. */
export class TooManySignInAttempts extends CredentialsSignin {
  override code = 'rate_limited'
}

interface SignInUser {
  id: string
  name: string | null
  email: string
  image: string | null
  passwordHash: string | null
}

export interface PasswordSignInDeps {
  findUser(email: string): Promise<SignInUser | null>
  compare(plain: string, hash: string): Promise<boolean>
  /** Compared against when no user exists, so timing does not reveal accounts. */
  dummyHash: string
}

/** The Credentials provider's `authorize`, with its limits. */
export async function authorizePassword(raw: unknown, request: Request, deps: PasswordSignInDeps) {
  const parsed = loginSchema.safeParse(raw)
  if (!parsed.success) return null
  const { email, password } = parsed.data // email is trimmed and lower-cased
  const emailKey = `login-email:${email}`

  const { perAddress, perEmail } = SIGN_IN_LIMITS
  const addressKey = clientKey(request, 'login')
  if (!rateLimit(addressKey, perAddress.limit, perAddress.windowMs).ok) {
    console.warn('sign-in refused: too many attempts from one address', { key: addressKey })
    throw new TooManySignInAttempts()
  }
  if (isLimited(emailKey, perEmail.limit)) {
    console.warn('sign-in refused: too many failed attempts for one email')
    throw new TooManySignInAttempts()
  }

  const user = await deps.findUser(email)
  const matches = await deps.compare(password, user?.passwordHash ?? deps.dummyHash)
  if (!user?.passwordHash || !matches) {
    rateLimit(emailKey, perEmail.limit, perEmail.windowMs)
    return null
  }

  clearLimit(emailKey)
  return { id: user.id, name: user.name, email: user.email, image: user.image }
}
