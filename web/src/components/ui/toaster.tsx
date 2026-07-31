'use client'

import { useTheme } from 'next-themes'
import { Toaster as SonnerToaster } from 'sonner'

export function Toaster() {
  const { resolvedTheme } = useTheme()

  return (
    <SonnerToaster
      theme={resolvedTheme === 'dark' ? 'dark' : 'light'}
      position="bottom-center"
      closeButton
      toastOptions={{
        classNames: {
          toast:
            'group rounded-lg border border-border bg-popover text-popover-foreground shadow-lg',
          description: 'text-muted-foreground',
        },
      }}
    />
  )
}
