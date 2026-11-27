'use client'

import { AlertTriangle, RotateCw } from 'lucide-react'
import Link from 'next/link'
import { useEffect } from 'react'

import { Button } from '@/components/ui/button'
import { ROUTES } from '@/lib/constants'

/** Route-level boundary: catches anything a page or its children throw. */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[app] route error')
  }, [error])
  const digest = typeof error.digest === 'string' && /^\d{1,20}$/.test(error.digest)
    ? error.digest
    : null

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-5 px-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertTriangle className="size-6" />
      </div>

      <div className="max-w-md">
        <h1 className="text-lg font-semibold">Something went wrong</h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          An unexpected error occurred while loading this page.
        </p>
        {digest && (
          // The digest is the only handle on the server-side stack, which is
          // deliberately not sent to the browser.
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            Reference: {digest}
          </p>
        )}
      </div>

      <div className="flex gap-2">
        <Button onClick={reset} className="gap-1.5">
          <RotateCw className="size-4" />
          Try again
        </Button>
        <Button variant="outline" asChild>
          <Link href={ROUTES.home}>Back to chats</Link>
        </Button>
      </div>
    </div>
  )
}
