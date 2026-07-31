'use client'

import {
  Check,
  Menu,
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  Share2,
  Trash2,
  X,
} from 'lucide-react'
import { useRouter } from 'next/navigation'
import * as React from 'react'

import { ModelPicker } from '@/components/chat/model-picker'
import { ShareDialog } from '@/components/chat/share-dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { useDeleteChat, useUpdateChat } from '@/hooks/use-chats'
import { ROUTES } from '@/lib/constants'
import { useUiStore } from '@/stores/ui-store'
import type { ChatDetail } from '@/types/chat'

interface ChatHeaderProps {
  chat: ChatDetail
  model: string
  onModelChange: (model: string) => void
  isBusy: boolean
}

export function ChatHeader({
  chat,
  model,
  onModelChange,
  isBusy,
}: ChatHeaderProps) {
  const router = useRouter()
  const updateChat = useUpdateChat()
  const deleteChat = useDeleteChat()
  const setMobileSidebarOpen = useUiStore((state) => state.setMobileSidebarOpen)

  const [isRenaming, setIsRenaming] = React.useState(false)
  const [draftTitle, setDraftTitle] = React.useState(chat.title)
  const [shareOpen, setShareOpen] = React.useState(false)
  const [confirmDelete, setConfirmDelete] = React.useState(false)

  React.useEffect(() => {
    setDraftTitle(chat.title)
  }, [chat.title])

  const commitRename = () => {
    const title = draftTitle.trim()
    setIsRenaming(false)

    if (!title || title === chat.title) {
      setDraftTitle(chat.title)
      return
    }
    updateChat.mutate({ chatId: chat.id, input: { title } })
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/90 px-3 backdrop-blur sm:px-4">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={() => setMobileSidebarOpen(true)}
      >
        <Menu />
        <span className="sr-only">Open chat list</span>
      </Button>

      {isRenaming ? (
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <Input
            autoFocus
            value={draftTitle}
            onChange={(event) => setDraftTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') commitRename()
              if (event.key === 'Escape') {
                setDraftTitle(chat.title)
                setIsRenaming(false)
              }
            }}
            onBlur={commitRename}
            aria-label="Chat title"
            className="h-8 max-w-md"
          />
          <Button variant="ghost" size="icon-sm" onClick={commitRename}>
            <Check />
            <span className="sr-only">Save title</span>
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => {
              setDraftTitle(chat.title)
              setIsRenaming(false)
            }}
          >
            <X />
            <span className="sr-only">Cancel rename</span>
          </Button>
        </div>
      ) : (
        <h1 className="min-w-0 flex-1 truncate text-sm font-semibold" title={chat.title}>
          {chat.title}
        </h1>
      )}

      <div className="flex shrink-0 items-center gap-1">
        <ModelPicker value={model} onChange={onModelChange} disabled={isBusy} />

        <Button
          variant="ghost"
          size="icon"
          onClick={() => setShareOpen(true)}
          className="hidden sm:inline-flex"
        >
          <Share2 />
          <span className="sr-only">Share chat</span>
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal />
              <span className="sr-only">Chat options</span>
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuItem onSelect={() => setIsRenaming(true)}>
              <Pencil />
              Rename
            </DropdownMenuItem>

            <DropdownMenuItem
              onSelect={() =>
                updateChat.mutate({
                  chatId: chat.id,
                  input: { pinned: !chat.pinned },
                })
              }
            >
              {chat.pinned ? <PinOff /> : <Pin />}
              {chat.pinned ? 'Unpin' : 'Pin to top'}
            </DropdownMenuItem>

            <DropdownMenuItem onSelect={() => setShareOpen(true)}>
              <Share2 />
              Share…
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              variant="destructive"
              onSelect={() => setConfirmDelete(true)}
            >
              <Trash2 />
              Delete chat
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <ShareDialog
        chatId={chat.id}
        chatTitle={chat.title}
        shareId={chat.shareId}
        open={shareOpen}
        onOpenChange={setShareOpen}
      />

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{chat.title}”?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the conversation and all of its messages. It cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                deleteChat.mutate(chat.id, {
                  onSuccess: () => router.push(ROUTES.home),
                })
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </header>
  )
}
