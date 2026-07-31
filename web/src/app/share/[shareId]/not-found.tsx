import { LinkIcon } from 'lucide-react'
import Link from 'next/link'

import { Button } from '@/components/ui/button'
import { ROUTES } from '@/lib/constants'

export default function SharedChatNotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <LinkIcon className="size-6" />
      </div>

      <div>
        <h1 className="text-lg font-semibold">This link is no longer available</h1>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          The conversation was unshared or deleted by its owner.
        </p>
      </div>

      <Button asChild>
        <Link href={ROUTES.home}>Go to LLM Dev Kit</Link>
      </Button>
    </div>
  )
}
