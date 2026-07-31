import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'

import { AuthCard } from '@/components/auth/auth-card'
import { OAuthButtons } from '@/components/auth/oauth-buttons'
import { RegisterForm } from '@/components/auth/register-form'
import { oauthProvidersEnabled } from '@/lib/auth'
import { ROUTES } from '@/lib/constants'
import { getEnv } from '@/lib/env'

export const metadata: Metadata = { title: 'Create an account' }

export default function RegisterPage() {
  if (!getEnv().ALLOW_REGISTRATION) {
    redirect(ROUTES.login)
  }

  const { github } = oauthProvidersEnabled()

  return (
    <AuthCard
      title="Create your account"
      description="Chats, folders and history stay tied to this account."
      footer={
        <>
          Already have an account?{' '}
          <Link
            href={ROUTES.login}
            className="font-medium text-primary hover:underline"
          >
            Sign in
          </Link>
        </>
      }
    >
      <OAuthButtons github={github} callbackUrl={ROUTES.home} />
      <RegisterForm callbackUrl={ROUTES.home} />
    </AuthCard>
  )
}
