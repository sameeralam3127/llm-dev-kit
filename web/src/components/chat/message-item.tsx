'use client'

import {
  AlertTriangle,
  Check,
  Copy,
  Link2,
  Pencil,
  RefreshCw,
  Sparkles,
  Trash2,
} from 'lucide-react'
import * as React from 'react'

import { MessageEditor } from '@/components/chat/message-editor'
import { VersionSwitcher } from '@/components/chat/version-switcher'
import { Markdown } from '@/components/markdown/markdown'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useCopy } from '@/hooks/use-copy'
import { cn, initialsOf } from '@/lib/utils'
import type { ChatMessage } from '@/types/chat'

interface MessageItemProps {
  message: ChatMessage
  /** True for the message currently receiving tokens. */
  isStreaming?: boolean
  isBusy?: boolean
  readOnly?: boolean
  user?: { name: string | null; image: string | null; email: string | null }
  onEdit?: (messageId: string, content: string) => void
  onRegenerate?: (messageId: string) => void
  onDelete?: (messageId: string) => void
}

export const MessageItem = React.memo(function MessageItem({
  message,
  isStreaming = false,
  isBusy = false,
  readOnly = false,
  user,
  onEdit,
  onRegenerate,
  onDelete,
}: MessageItemProps) {
  const [isEditing, setIsEditing] = React.useState(false)
  const { copied, copy } = useCopy()

  const isUser = message.role === 'user'

  // Newest content lives on the message; older ones are archived versions, so
  // the visible list is [...archived, current] and the last index is current.
  const allVersions = React.useMemo(
    () => [...message.versions.map((version) => version.content), message.content],
    [message.versions, message.content],
  )
  const [versionIndex, setVersionIndex] = React.useState(allVersions.length - 1)

  // A regeneration appends a version; follow it rather than stranding the
  // reader on the answer they just replaced.
  React.useEffect(() => {
    setVersionIndex(allVersions.length - 1)
  }, [allVersions.length])

  const displayed = allVersions[Math.min(versionIndex, allVersions.length - 1)] ?? ''
  const isViewingOlder = versionIndex !== allVersions.length - 1

  const copyLink = () => {
    const url = new URL(window.location.href)
    url.hash = `message-${message.id}`
    void copy(url.toString(), 'Link copied')
  }

  if (isEditing && isUser) {
    return (
      <article
        id={`message-${message.id}`}
        className="flex w-full gap-3 px-4 py-5 sm:px-6"
      >
        <MessageAvatar isUser user={user} />
        <MessageEditor
          initialContent={message.content}
          onCancel={() => setIsEditing(false)}
          onSubmit={(content) => {
            setIsEditing(false)
            onEdit?.(message.id, content)
          }}
        />
      </article>
    )
  }

  return (
    <article
      id={`message-${message.id}`}
      // `group` drives the hover-reveal of the action row on pointer devices;
      // focus-within keeps it reachable by keyboard.
      className={cn(
        'group flex w-full gap-3 px-4 py-5 sm:px-6',
        isUser ? 'bg-transparent' : 'bg-muted/30',
      )}
      aria-label={isUser ? 'Your message' : 'Assistant response'}
    >
      <MessageAvatar isUser={isUser} user={user} />

      <div className="min-w-0 flex-1">
        <header className="mb-1 flex items-center gap-2">
          <h3 className="text-sm font-semibold">
            {isUser ? (user?.name ?? 'You') : 'Assistant'}
          </h3>

          {message.editedAt && (
            <Badge variant="secondary" className="font-normal">
              edited
            </Badge>
          )}

          {!isUser && message.model && (
            <span className="truncate font-mono text-xs text-muted-foreground">
              {message.model}
            </span>
          )}

          {isViewingOlder && (
            <Badge variant="outline" className="font-normal">
              older version
            </Badge>
          )}
        </header>

        {isUser ? (
          <div className="whitespace-pre-wrap break-words text-[0.9375rem] leading-7">
            {displayed}
          </div>
        ) : (
          <>
            {displayed ? (
              <Markdown
                content={displayed}
                className={cn(isStreaming && 'streaming-caret')}
              />
            ) : (
              isStreaming && <ThinkingIndicator />
            )}

            {message.error && (
              <div
                role="alert"
                className="mt-3 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium">Generation failed</p>
                  <p className="break-words opacity-90">{message.error}</p>
                </div>
              </div>
            )}

            {message.truncated && !message.error && displayed && (
              <p className="mt-2 text-xs text-muted-foreground">
                Response stopped early.
              </p>
            )}
          </>
        )}

        {!readOnly && !isStreaming && (
          <div
            className={cn(
              'mt-2 flex items-center gap-0.5 transition-opacity',
              // Always visible on touch, where there is no hover to reveal it.
              'opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100',
            )}
          >
            {!isUser && (
              <VersionSwitcher
                index={versionIndex}
                total={allVersions.length}
                onChange={setVersionIndex}
              />
            )}

            <ActionButton
              label={copied ? 'Copied' : 'Copy message'}
              onClick={() => void copy(displayed, 'Message copied')}
            >
              {copied ? <Check className="text-emerald-500" /> : <Copy />}
            </ActionButton>

            <ActionButton label="Copy link to this message" onClick={copyLink}>
              <Link2 />
            </ActionButton>

            {isUser && onEdit && (
              <ActionButton
                label="Edit message"
                disabled={isBusy}
                onClick={() => setIsEditing(true)}
              >
                <Pencil />
              </ActionButton>
            )}

            {!isUser && onRegenerate && (
              <ActionButton
                label="Regenerate response"
                disabled={isBusy}
                onClick={() => onRegenerate(message.id)}
              >
                <RefreshCw />
              </ActionButton>
            )}

            {!isUser && onDelete && message.error && (
              <ActionButton
                label="Remove this response"
                disabled={isBusy}
                onClick={() => onDelete(message.id)}
              >
                <Trash2 />
              </ActionButton>
            )}
          </div>
        )}
      </div>
    </article>
  )
})

function MessageAvatar({
  isUser,
  user,
}: {
  isUser: boolean
  user?: { name: string | null; image: string | null; email: string | null }
}) {
  if (!isUser) {
    return (
      <div
        aria-hidden="true"
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary"
      >
        <Sparkles className="size-4" />
      </div>
    )
  }

  return (
    <Avatar className="shrink-0">
      {user?.image && <AvatarImage src={user.image} alt="" />}
      <AvatarFallback>{initialsOf(user?.name ?? user?.email)}</AvatarFallback>
    </Avatar>
  )
}

function ActionButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  children: React.ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onClick}
          disabled={disabled}
          className="text-muted-foreground hover:text-foreground"
        >
          {children}
          <span className="sr-only">{label}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  )
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1" aria-label="Generating response">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="size-1.5 animate-pulse rounded-full bg-muted-foreground/60"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  )
}
