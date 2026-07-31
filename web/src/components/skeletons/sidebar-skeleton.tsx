import { Skeleton } from '@/components/ui/skeleton'

export function ChatListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div
      className="space-y-1 px-2"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <span className="sr-only">Loading chats…</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="flex items-center gap-2 rounded-md px-2 py-2">
          <Skeleton className="size-4 shrink-0 rounded" />
          <Skeleton
            className="h-3.5 flex-1"
            // Varied widths read as a list of titles rather than a table.
            style={{ maxWidth: `${60 + ((index * 13) % 35)}%` }}
          />
        </div>
      ))}
    </div>
  )
}

export function FolderListSkeleton() {
  return (
    <div className="space-y-1 px-2" aria-hidden="true">
      {Array.from({ length: 3 }, (_, index) => (
        <div key={index} className="flex items-center gap-2 px-2 py-1.5">
          <Skeleton className="size-2 rounded-full" />
          <Skeleton className="h-3 w-24" />
        </div>
      ))}
    </div>
  )
}
