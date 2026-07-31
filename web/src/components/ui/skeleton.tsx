import { cn } from '@/lib/utils'

/**
 * Placeholder block. `aria-hidden` because the surrounding region announces its
 * own busy state — a screen reader should hear "loading messages", not a dozen
 * anonymous boxes.
 */
function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  )
}

export { Skeleton }
