import { MessageSquareOff } from 'lucide-react'
import Link from 'next/link'

import { Button } from '@/components/ui/button'
import { ROUTES } from '@/lib/constants'

export default function ChatNotFound() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <MessageSquareOff className="size-6" />
      </div>

      <div>
        <h1 className="text-lg font-semibold">Chat not found</h1>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          It may have been deleted, or it belongs to another account.
        </p>
      </div>

      <Button asChild>
        <Link href={ROUTES.home}>Back to chats</Link>
      </Button>
    </div>
  )
}
