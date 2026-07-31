import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

function MessageSkeleton({ isUser = false }: { isUser?: boolean }) {
  return (
    <div className={cn('flex gap-3 px-4 py-5 sm:px-6', !isUser && 'bg-muted/30')}>
      <Skeleton className="size-8 shrink-0 rounded-full" />
      <div className="min-w-0 flex-1 space-y-2.5">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-[92%]" />
        {!isUser && <Skeleton className="h-3.5 w-[70%]" />}
      </div>
    </div>
  )
}

/**
 * One live region announces the whole transcript as loading; the individual
 * blocks are `aria-hidden`, so assistive tech hears one message, not six.
 */
export function MessageListSkeleton() {
  return (
    <div
      className="mx-auto w-full max-w-3xl"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="sr-only">Loading conversation…</span>
      <MessageSkeleton isUser />
      <MessageSkeleton />
      <MessageSkeleton isUser />
      <MessageSkeleton />
    </div>
  )
}
