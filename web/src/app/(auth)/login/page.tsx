import type { Metadata } from 'next'
import Link from 'next/link'

import { AuthCard } from '@/components/auth/auth-card'
import { LoginForm } from '@/components/auth/login-form'
import { OAuthButtons } from '@/components/auth/oauth-buttons'
import { oauthProvidersEnabled } from '@/lib/auth'
import { ROUTES } from '@/lib/constants'
import { getEnv } from '@/lib/env'

export const metadata: Metadata = { title: 'Sign in' }

interface PageProps {
  searchParams: Promise<{ callbackUrl?: string }>
}

/**
 * Only same-origin relative paths are accepted, so a crafted
 * `?callbackUrl=https://evil.example` cannot turn sign-in into an open redirect.
 */
function safeCallback(raw: string | undefined): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return ROUTES.home
  return raw
}

export default async function LoginPage({ searchParams }: PageProps) {
  const { callbackUrl } = await searchParams
  const target = safeCallback(callbackUrl)
  const { github } = oauthProvidersEnabled()
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
      <OAuthButtons github={github} callbackUrl={target} />
      <LoginForm callbackUrl={target} />
    </AuthCard>
  )
}
