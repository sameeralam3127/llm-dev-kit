'use client'

import { ChevronRight, FolderOpen, MoreHorizontal, Pencil, Trash2 } from 'lucide-react'
import * as React from 'react'

import { ChatListItem } from '@/components/sidebar/chat-list-item'
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useDeleteFolder, useUpdateFolder } from '@/hooks/use-folders'
import { FOLDER_COLORS, folderColor } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { ChatSummary, Folder } from '@/types/chat'

interface FolderSectionProps {
  folder: Folder
  chats: ChatSummary[]
  allFolders: Folder[]
  activeChatId: string | null
  isExpanded: boolean
  onToggle: () => void
  onNavigate?: () => void
}

export function FolderSection({
  folder,
  chats,
  allFolders,
  activeChatId,
  isExpanded,
  onToggle,
  onNavigate,
}: FolderSectionProps) {
  const updateFolder = useUpdateFolder()
  const deleteFolder = useDeleteFolder()

  const [isRenaming, setIsRenaming] = React.useState(false)
  const [draft, setDraft] = React.useState(folder.name)
  const [confirmDelete, setConfirmDelete] = React.useState(false)

  const color = folderColor(folder.color)

  const commitRename = () => {
    const name = draft.trim()
    setIsRenaming(false)

    if (!name || name === folder.name) {
      setDraft(folder.name)
      return
    }
    updateFolder.mutate({ folderId: folder.id, input: { name } })
  }

  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <div className="group/folder relative px-2">
        {isRenaming ? (
          <div className="flex items-center gap-1 rounded-md bg-sidebar-accent px-2 py-1">
            <span className={cn('size-2 shrink-0 rounded-full', color.dot)} />
            <input
              autoFocus
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') commitRename()
                if (event.key === 'Escape') {
                  setDraft(folder.name)
                  setIsRenaming(false)
                }
              }}
              onBlur={commitRename}
              aria-label="Folder name"
              className="min-w-0 flex-1 bg-transparent py-1 text-xs font-medium outline-none"
            />
          </div>
        ) : (
          <CollapsibleTrigger
            className={cn(
              'flex w-full items-center gap-1.5 rounded-md py-1.5 pl-1 pr-8 text-xs font-medium transition-colors',
              'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
            )}
          >
            <ChevronRight
              className={cn(
                'size-3.5 shrink-0 transition-transform',
                isExpanded && 'rotate-90',
              )}
              aria-hidden="true"
            />
            <span className={cn('size-2 shrink-0 rounded-full', color.dot)} />
            <span className="min-w-0 flex-1 truncate text-left">{folder.name}</span>
            <span className="shrink-0 tabular-nums opacity-60">{chats.length}</span>
          </CollapsibleTrigger>
        )}

        <div
          className={cn(
            'absolute right-3 top-1/2 -translate-y-1/2 transition-opacity',
            'opacity-0 focus-within:opacity-100 group-hover/folder:opacity-100',
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
                <span className="sr-only">Options for folder {folder.name}</span>
              </Button>
            </DropdownMenuTrigger>

            <DropdownMenuContent align="start" side="right" className="w-48">
              <DropdownMenuItem onSelect={() => setIsRenaming(true)}>
                <Pencil />
                Rename
              </DropdownMenuItem>

              <DropdownMenuSeparator />
              <DropdownMenuLabel>Colour</DropdownMenuLabel>

              <div className="flex flex-wrap gap-1 p-1.5">
                {FOLDER_COLORS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() =>
                      updateFolder.mutate({
                        folderId: folder.id,
                        input: { color: option.id },
                      })
                    }
                    aria-label={option.label}
                    aria-pressed={folder.color === option.id}
                    className={cn(
                      'size-5 rounded-full ring-offset-2 ring-offset-popover transition',
                      option.dot,
                      folder.color === option.id && 'ring-2 ring-ring',
                    )}
                  />
                ))}
              </div>

              <DropdownMenuSeparator />

              <DropdownMenuItem
                variant="destructive"
                onSelect={() => setConfirmDelete(true)}
              >
                <Trash2 />
                Delete folder
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <CollapsibleContent>
        {chats.length === 0 ? (
          <p className="px-2 py-2 pl-8 text-xs text-muted-foreground">
            No chats yet
          </p>
        ) : (
          <ul className="mt-0.5 space-y-0.5 pl-3">
            {chats.map((chat) => (
              <ChatListItem
                key={chat.id}
                chat={chat}
                isActive={chat.id === activeChatId}
                folders={allFolders}
                {...(onNavigate ? { onNavigate } : {})}
              />
            ))}
          </ul>
        )}
      </CollapsibleContent>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <FolderOpen className="size-4" />
              Delete “{folder.name}”?
            </AlertDialogTitle>
            <AlertDialogDescription>
              The {chats.length} chat{chats.length === 1 ? '' : 's'} inside will move
              to All chats. Nothing is deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteFolder.mutate(folder.id)}
            >
              Delete folder
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Collapsible>
  )
}
