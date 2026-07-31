'use client'

import { Github } from 'lucide-react'
import { signIn } from 'next-auth/react'
import * as React from 'react'

import { Button } from '@/components/ui/button'

interface OAuthButtonsProps {
  github: boolean
  callbackUrl: string
}

export function OAuthButtons({ github, callbackUrl }: OAuthButtonsProps) {
  const [pending, setPending] = React.useState(false)

  if (!github) return null

  return (
    <>
      <Button
        type="button"
        variant="outline"
        className="w-full gap-2"
        disabled={pending}
        onClick={() => {
          setPending(true)
          void signIn('github', { callbackUrl })
        }}
      >
        <Github className="size-4" />
        Continue with GitHub
      </Button>

      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <span className="w-full border-t border-border" />
        </div>
        <div className="relative flex justify-center">
          <span className="bg-card px-2 text-xs uppercase tracking-wide text-muted-foreground">
            or
          </span>
        </div>
      </div>
    </>
  )
}
