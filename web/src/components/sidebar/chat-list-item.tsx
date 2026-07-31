'use client'

import { formatDistanceToNow } from 'date-fns'
import {
  Check,
  FolderInput,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  Trash2,
  X,
} from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import * as React from 'react'

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
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useDeleteChat, useUpdateChat } from '@/hooks/use-chats'
import { folderColor, ROUTES } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { ChatSummary, Folder } from '@/types/chat'

interface ChatListItemProps {
  chat: ChatSummary
  isActive: boolean
  folders: Folder[]
  onNavigate?: () => void
}

export function ChatListItem({
  chat,
  isActive,
  folders,
  onNavigate,
}: ChatListItemProps) {
  const router = useRouter()
  const updateChat = useUpdateChat()
  const deleteChat = useDeleteChat()

  const [isRenaming, setIsRenaming] = React.useState(false)
  const [draft, setDraft] = React.useState(chat.title)
  const [confirmDelete, setConfirmDelete] = React.useState(false)

  const commitRename = () => {
    const title = draft.trim()
    setIsRenaming(false)

    if (!title || title === chat.title) {
      setDraft(chat.title)
      return
    }
    updateChat.mutate({ chatId: chat.id, input: { title } })
  }

  if (isRenaming) {
    return (
      <li className="px-2">
        <div className="flex items-center gap-1 rounded-md bg-sidebar-accent px-1.5 py-1">
          <input
            autoFocus
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') commitRename()
              if (event.key === 'Escape') {
                setDraft(chat.title)
                setIsRenaming(false)
              }
            }}
            onBlur={commitRename}
            aria-label="Chat title"
            className="min-w-0 flex-1 bg-transparent px-1 py-1 text-sm outline-none"
          />
          <Button variant="ghost" size="icon-sm" onMouseDown={commitRename}>
            <Check className="size-3.5" />
            <span className="sr-only">Save</span>
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onMouseDown={() => {
              setDraft(chat.title)
              setIsRenaming(false)
            }}
          >
            <X className="size-3.5" />
            <span className="sr-only">Cancel</span>
          </Button>
        </div>
      </li>
    )
  }

  return (
    <li className="group/item relative px-2">
      <Link
        href={ROUTES.chat(chat.id)}
        onClick={onNavigate}
        aria-current={isActive ? 'page' : undefined}
        className={cn(
          'flex items-center gap-2 rounded-md py-2 pl-2 pr-8 text-sm transition-colors',
          isActive
            ? 'bg-sidebar-accent font-medium text-foreground'
            : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
        )}
      >
        {chat.pinned ? (
          <Pin className="size-3.5 shrink-0 fill-current opacity-70" />
        ) : (
          <MessageSquare className="size-3.5 shrink-0 opacity-70" />
        )}

        <span className="min-w-0 flex-1 truncate">{chat.title}</span>
      </Link>

      <div
        className={cn(
          'absolute right-3 top-1/2 -translate-y-1/2 transition-opacity',
          'opacity-0 focus-within:opacity-100 group-hover/item:opacity-100',
          // Touch devices never hover, so the menu stays visible there.
          '[@media(pointer:coarse)]:opacity-100',
        )}
      >
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              className="size-6 hover:bg-background"
            >
              <MoreHorizontal className="size-3.5" />
              <span className="sr-only">Options for {chat.title}</span>
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="start" side="right" className="w-52">
            <div className="px-2 py-1.5">
              <p className="truncate text-xs font-medium">{chat.title}</p>
              <p className="text-xs text-muted-foreground">
                {chat.messageCount} message{chat.messageCount === 1 ? '' : 's'} ·{' '}
                {formatDistanceToNow(new Date(chat.updatedAt), { addSuffix: true })}
              </p>
            </div>

            <DropdownMenuSeparator />

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

            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <FolderInput />
                Move to
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-48">
                <DropdownMenuItem
                  disabled={chat.folderId === null}
                  onSelect={() =>
                    updateChat.mutate({
                      chatId: chat.id,
                      input: { folderId: null },
                    })
                  }
                >
                  No folder
                </DropdownMenuItem>

                {folders.length > 0 && <DropdownMenuSeparator />}

                {folders.map((folder) => (
                  <DropdownMenuItem
                    key={folder.id}
                    disabled={chat.folderId === folder.id}
                    onSelect={() =>
                      updateChat.mutate({
                        chatId: chat.id,
                        input: { folderId: folder.id },
                      })
                    }
                  >
                    <span
                      className={cn(
                        'size-2 shrink-0 rounded-full',
                        folderColor(folder.color).dot,
                      )}
                    />
                    <span className="truncate">{folder.name}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuSubContent>
            </DropdownMenuSub>

            <DropdownMenuSeparator />

            <DropdownMenuItem
              variant="destructive"
              onSelect={() => setConfirmDelete(true)}
            >
              <Trash2 />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

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
              onClick={() =>
                deleteChat.mutate(chat.id, {
                  onSuccess: () => {
                    // Only navigate away if the chat being deleted is on screen.
                    if (isActive) router.push(ROUTES.home)
                  },
                })
              }
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  )
}
