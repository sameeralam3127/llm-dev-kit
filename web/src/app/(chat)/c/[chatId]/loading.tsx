import { MessageListSkeleton } from '@/components/skeletons/message-skeleton'
import { Skeleton } from '@/components/ui/skeleton'

export default function ChatLoading() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 shrink-0 items-center gap-3 border-b border-border px-4">
        <Skeleton className="h-4 w-48" />
        <div className="ml-auto flex items-center gap-2">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="size-8 rounded-md" />
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <MessageListSkeleton />
      </div>

      <div className="border-t border-border p-4">
        <Skeleton className="mx-auto h-14 w-full max-w-3xl rounded-2xl" />
      </div>
    </div>
  )
}
