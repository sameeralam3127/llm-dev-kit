'use client'

import { AlertTriangle, RotateCw } from 'lucide-react'
import * as React from 'react'

import { Button } from '@/components/ui/button'

interface ErrorBoundaryProps {
  children: React.ReactNode
  /** Rendered instead of the default panel; receives a reset callback. */
  fallback?: (error: Error, reset: () => void) => React.ReactNode
  onError?: (error: Error, info: React.ErrorInfo) => void
}

interface ErrorBoundaryState {
  error: Error | null
}

/**
 * Catches render-time crashes in a subtree.
 *
 * React has no hook equivalent, so this stays a class. Next's `error.tsx` files
 * cover route segments; this one wraps the smaller pieces — a single message, a
 * markdown block — where a crash should not take the whole page down.
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  override state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  override componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.props.onError?.(error, info)
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  private reset = () => {
    this.setState({ error: null })
  }

  override render() {
    const { error } = this.state
    if (!error) return this.props.children

    if (this.props.fallback) return this.props.fallback(error, this.reset)

    return (
      <div
        role="alert"
        className="m-4 rounded-lg border border-destructive/40 bg-destructive/5 p-4"
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-destructive" />
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">Something broke here</h2>
            <p className="mt-1 break-words text-sm text-muted-foreground">
              {error.message || 'An unexpected error occurred.'}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={this.reset}
              className="mt-3 gap-1.5"
            >
              <RotateCw className="size-3.5" />
              Try again
            </Button>
          </div>
        </div>
      </div>
    )
  }
}
