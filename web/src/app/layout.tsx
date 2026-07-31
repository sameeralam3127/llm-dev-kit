import type { Metadata, Viewport } from 'next'

import { Providers } from '@/components/providers'
import { Toaster } from '@/components/ui/toaster'

import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'LLM Dev Kit — Chat',
    template: '%s · LLM Dev Kit',
  },
  description:
    'A local-first AI chat workspace with retrieval-augmented answers, chat folders and shareable conversations.',
  robots: { index: false, follow: false },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#14161a' },
  ],
  width: 'device-width',
  initialScale: 1,
  // Zoom stays enabled: disabling it fails WCAG 1.4.4.
  maximumScale: 5,
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning: next-themes sets the class on <html> before
    // React hydrates, which is a deliberate mismatch.
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-dvh bg-background font-sans text-foreground">
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}
