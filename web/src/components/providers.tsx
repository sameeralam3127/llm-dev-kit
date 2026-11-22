'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SessionProvider } from 'next-auth/react'
import { ThemeProvider } from 'next-themes'
import { useState } from 'react'

import { TooltipProvider } from '@/components/ui/tooltip'
import { ApiClientError } from '@/lib/api-client'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Retrying a 4xx just repeats the same rejection.
          if (error instanceof ApiClientError && error.status < 500) return false
          return failureCount < 2
        },
      },
      mutations: { retry: false },
    },
  })
}

export function Providers({ children, nonce }: { children: React.ReactNode; nonce?: string }) {
  // Created in state, not at module scope: a module-level client would be
  // shared across requests on the server and leak one user's data to the next.
  const [queryClient] = useState(makeQueryClient)

  return (
    <SessionProvider>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider
          attribute="class"
          // Follow the operating system until the user picks a theme.
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
          // The theme script runs before hydration; the CSP needs its nonce.
          nonce={nonce}
        >
          <TooltipProvider delayDuration={300} skipDelayDuration={0}>
            {children}
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </SessionProvider>
  )
}
