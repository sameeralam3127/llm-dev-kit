'use client'

import { FolderPlus, PenSquare, Search, X } from 'lucide-react'
import { useParams } from 'next/navigation'
import * as React from 'react'

import { ChatListItem } from '@/components/sidebar/chat-list-item'
import { FolderSection } from '@/components/sidebar/folder-section'
import { NewFolderDialog } from '@/components/sidebar/new-folder-dialog'
import { UserMenu } from '@/components/sidebar/user-menu'
import {
  ChatListSkeleton,
  FolderListSkeleton,
} from '@/components/skeletons/sidebar-skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useChats, useCreateChat } from '@/hooks/use-chats'
import { useFolders } from '@/hooks/use-folders'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import { useUiStore } from '@/stores/ui-store'
import type { ChatSummary } from '@/types/chat'

interface SidebarProps {
  user: { name: string | null; email: string | null; image: string | null }
  /** Closes the mobile drawer after navigating. */
  onNavigate?: () => void
}

export function Sidebar({ user, onNavigate }: SidebarProps) {
  const params = useParams<{ chatId?: string }>()
  const activeChatId = params?.chatId ?? null

  const [search, setSearch] = React.useState('')
  const debouncedSearch = useDebouncedValue(search, 250)
  const searchRef = React.useRef<HTMLInputElement>(null)

  const { data: chats, isLoading: chatsLoading } = useChats(
    debouncedSearch ? { q: debouncedSearch } : {},
  )
  const { data: folders, isLoading: foldersLoading } = useFolders()
  const createChat = useCreateChat()
  const [newFolderOpen, setNewFolderOpen] = React.useState(false)

  const expandedFolderIds = useUiStore((state) => state.expandedFolderIds)
  const toggleFolder = useUiStore((state) => state.toggleFolder)

  // ⌘K / Ctrl+K focuses search — the shortcut people already expect.
  React.useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        searchRef.current?.focus()
        searchRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const { grouped, ungrouped } = React.useMemo(() => {
    const byFolder = new Map<string, ChatSummary[]>()
    const loose: ChatSummary[] = []

    for (const chat of chats ?? []) {
      if (chat.folderId) {
        const existing = byFolder.get(chat.folderId) ?? []
        existing.push(chat)
        byFolder.set(chat.folderId, existing)
      } else {
        loose.push(chat)
      }
    }

    return { grouped: byFolder, ungrouped: loose }
  }, [chats])

  const isSearching = debouncedSearch.length > 0
  const hasNothing =
    !chatsLoading && (chats?.length ?? 0) === 0 && (folders?.length ?? 0) === 0

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex flex-col gap-2 p-3">
        <div className="flex items-center gap-1.5">
          <Button
            className="flex-1 justify-start gap-2"
            onClick={() => createChat.mutate({})}
            disabled={createChat.isPending}
          >
            <PenSquare className="size-4" />
            New chat
          </Button>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setNewFolderOpen(true)}
              >
                <FolderPlus />
                <span className="sr-only">New folder</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>New folder</TooltipContent>
          </Tooltip>
        </div>

        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            ref={searchRef}
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setSearch('')
            }}
            placeholder="Search chats…"
            aria-label="Search chats"
            className="h-8 bg-background pl-8 pr-8 text-sm [&::-webkit-search-cancel-button]:hidden"
          />
          {search && (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => {
                setSearch('')
                searchRef.current?.focus()
              }}
              className="absolute right-0.5 top-1/2 size-7 -translate-y-1/2"
            >
              <X className="size-3.5" />
              <span className="sr-only">Clear search</span>
            </Button>
          )}
        </div>
      </div>

      <nav
        className="scrollbar-thin flex-1 overflow-y-auto pb-3"
        aria-label="Chat history"
      >
        {chatsLoading || foldersLoading ? (
          <div className="space-y-4">
            <FolderListSkeleton />
            <ChatListSkeleton />
          </div>
        ) : hasNothing ? (
          <p className="px-5 py-8 text-center text-sm text-muted-foreground">
            No chats yet. Start one to see it here.
          </p>
        ) : (
          <>
            {/* Folders are hidden while searching: results are ranked by match,
                not by where they happen to be filed. */}
            {!isSearching && (folders?.length ?? 0) > 0 && (
              <section className="mb-3 space-y-0.5" aria-label="Folders">
                {folders?.map((folder) => (
                  <FolderSection
                    key={folder.id}
                    folder={folder}
                    chats={grouped.get(folder.id) ?? []}
                    allFolders={folders}
                    activeChatId={activeChatId}
                    isExpanded={expandedFolderIds.includes(folder.id)}
                    onToggle={() => toggleFolder(folder.id)}
                    {...(onNavigate ? { onNavigate } : {})}
                  />
                ))}
              </section>
            )}

            <section aria-label={isSearching ? 'Search results' : 'All chats'}>
              <h2 className="px-4 pb-1 pt-1 text-xs font-medium text-muted-foreground">
                {isSearching
                  ? `${chats?.length ?? 0} result${(chats?.length ?? 0) === 1 ? '' : 's'}`
                  : 'All chats'}
              </h2>

              {(isSearching ? (chats ?? []) : ungrouped).length === 0 ? (
                <p className="px-4 py-3 text-sm text-muted-foreground">
                  {isSearching ? 'Nothing matched that search.' : 'No loose chats.'}
                </p>
              ) : (
                <ul className="space-y-0.5">
                  {(isSearching ? (chats ?? []) : ungrouped).map((chat) => (
                    <ChatListItem
                      key={chat.id}
                      chat={chat}
                      isActive={chat.id === activeChatId}
                      folders={folders ?? []}
                      {...(onNavigate ? { onNavigate } : {})}
                    />
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </nav>

      <div className="border-t border-sidebar-border p-2">
        <UserMenu user={user} />
      </div>

      <NewFolderDialog open={newFolderOpen} onOpenChange={setNewFolderOpen} />
    </div>
  )
}
