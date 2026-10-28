import type { Metadata } from 'next'
import Link from 'next/link'

import { AuthCard } from '@/components/auth/auth-card'
import { LoginForm } from '@/components/auth/login-form'
import { OAuthButtons } from '@/components/auth/oauth-buttons'
import { oauthProvidersEnabled } from '@/lib/auth'
import { ROUTES } from '@/lib/constants'
import { getEnv } from '@/lib/env'
import { safeCallback } from '@/lib/safe-callback'

export const metadata: Metadata = { title: 'Sign in' }

interface PageProps {
  searchParams: Promise<{ callbackUrl?: string; error?: string }>
}

/** What Auth.js's `?error=` codes mean to the person signing in. */
const SIGN_IN_ERRORS: Record<string, string> = {
  OAuthAccountNotLinked:
    'That email already has an account here. Sign in with its password instead: accounts are not linked by email, so owning the same address elsewhere cannot take one over.',
  AccessDenied: 'Access was denied.',
  Configuration: 'Sign-in is misconfigured on this server. Ask your administrator to check its logs.',
}

function signInError(code: string | undefined): string | undefined {
  if (!code || code === 'CredentialsSignin') return undefined
  return SIGN_IN_ERRORS[code] ?? 'Sign-in did not complete. Try again.'
}

export default async function LoginPage({ searchParams }: PageProps) {
  const { callbackUrl, error } = await searchParams
  const target = safeCallback(callbackUrl)
  const { github, sso } = oauthProvidersEnabled()
  const initialError = signInError(error)
  const allowRegistration = getEnv().ALLOW_REGISTRATION

  return (
    <AuthCard
      title="Welcome back"
      description="Sign in to pick up your conversations."
      footer={
        allowRegistration ? (
          <>
            Don&apos;t have an account?{' '}
            <Link
              href={ROUTES.register}
              className="font-medium text-primary hover:underline"
            >
              Create one
            </Link>
          </>
        ) : (
          'Registration is disabled on this instance.'
        )
      }
    >
      <OAuthButtons github={github} sso={sso} callbackUrl={target} />
      <LoginForm callbackUrl={target} {...(initialError ? { initialError } : {})} />
    </AuthCard>
  )
}
