'use client'

import { Check, Copy, Globe, Loader2, Lock } from 'lucide-react'
import * as React from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useCopy } from '@/hooks/use-copy'
import { useUpdateChat } from '@/hooks/use-chats'
import { ROUTES } from '@/lib/constants'

interface ShareDialogProps {
  chatId: string
  chatTitle: string
  shareId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ShareDialog({
  chatId,
  chatTitle,
  shareId,
  open,
  onOpenChange,
}: ShareDialogProps) {
  const updateChat = useUpdateChat()
  const { copied, copy } = useCopy()

  // Built on the client so the link matches whatever host the user is on,
  // rather than a base URL baked in at build time.
  const shareUrl = React.useMemo(() => {
    if (!shareId || typeof window === 'undefined') return ''
    return `${window.location.origin}${ROUTES.share(shareId)}`
  }, [shareId])

  const isShared = Boolean(shareId)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Share this chat</DialogTitle>
          <DialogDescription>
            Anyone with the link can read “{chatTitle}”. They cannot reply to it
            or see your other chats.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center justify-between rounded-lg border border-border p-3">
          <div className="flex items-center gap-3">
            {isShared ? (
              <Globe className="size-4 text-primary" />
            ) : (
              <Lock className="size-4 text-muted-foreground" />
            )}
            <div>
              <Label htmlFor="share-toggle" className="cursor-pointer">
                {isShared ? 'Public link is on' : 'Private'}
              </Label>
              <p className="text-xs text-muted-foreground">
                {isShared
                  ? 'Turning this off breaks the existing link.'
                  : 'Create a read-only link to this conversation.'}
              </p>
            </div>
          </div>

          <Switch
            id="share-toggle"
            checked={isShared}
            disabled={updateChat.isPending}
            onCheckedChange={(checked) =>
              updateChat.mutate({ chatId, input: { shared: checked } })
            }
          />
        </div>

        {isShared && shareUrl && (
          <div className="space-y-2">
            <Label htmlFor="share-url">Link</Label>
            <div className="flex gap-2">
              <Input
                id="share-url"
                readOnly
                value={shareUrl}
                onFocus={(event) => event.currentTarget.select()}
                className="font-mono text-xs"
              />
              <Button
                variant="secondary"
                size="icon"
                onClick={() => void copy(shareUrl, 'Share link copied')}
              >
                {copied ? <Check className="text-emerald-500" /> : <Copy />}
                <span className="sr-only">Copy share link</span>
              </Button>
            </div>
          </div>
        )}

        <DialogFooter>
          {updateChat.isPending && (
            <span className="mr-auto flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              Updating…
            </span>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
