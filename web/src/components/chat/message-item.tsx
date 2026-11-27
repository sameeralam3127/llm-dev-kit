'use client'

import {
  AlertTriangle,
  Check,
  Copy,
  Link2,
  Pencil,
  RefreshCw,
  Trash2,
} from 'lucide-react'
import * as React from 'react'

import { BrandMark } from '@/components/brand/brand-mark'
import { MessageEditor } from '@/components/chat/message-editor'
import { MessageSources } from '@/components/chat/message-sources'
import { VersionSwitcher } from '@/components/chat/version-switcher'
import { CitationProvider } from '@/components/markdown/citations'
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
import type { ChatMessage, MessageSource } from '@/types/chat'

const NO_SOURCES: MessageSource[] = []

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

  // Sources belong to the current answer; archived versions did not keep theirs.
  const sources = isViewingOlder ? NO_SOURCES : message.sources
  const sourceIdPrefix = `message-${message.id}-source`
  const [sourcesOpen, setSourcesOpen] = React.useState(false)
  const [activeSource, setActiveSource] = React.useState<number | null>(null)
  const highlightTimer = React.useRef<number | undefined>(undefined)

  React.useEffect(() => () => window.clearTimeout(highlightTimer.current), [])

  const citations = React.useMemo(
    () => ({
      available: new Set(sources.map((source) => source.index)),
      idFor: (n: number) => `${sourceIdPrefix}-${n}`,
      onActivate: (n: number) => {
        setSourcesOpen(true)
        setActiveSource(n)
        window.clearTimeout(highlightTimer.current)
        highlightTimer.current = window.setTimeout(() => setActiveSource(null), 1600)
      },
    }),
    [sources, sourceIdPrefix],
  )

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

  // A failed, empty answer has nothing to copy or link to, and its card
  // already offers Retry; the row would only repeat it.
  const actionRow = !readOnly && !isStreaming && !(message.error && !displayed) && (
    <div
      className={cn(
        'mt-2 flex items-center gap-0.5 transition-opacity',
        isUser && 'justify-end',
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

    </div>
  )

  if (isUser) {
    return (
      <article
        id={`message-${message.id}`}
        className="group flex w-full animate-message-in items-start justify-end gap-3 px-4 py-3 sm:px-6"
        aria-label="Your message"
      >
        <div className="flex min-w-0 max-w-[85%] flex-col items-end sm:max-w-[70%]">
          <div className="rounded-2xl rounded-br-md bg-secondary px-4 py-2.5 text-[0.9375rem] leading-7 text-secondary-foreground">
            <div className="whitespace-pre-wrap break-words">{displayed}</div>
          </div>

          {message.editedAt && (
            <Badge variant="secondary" className="mt-1 font-normal">
              edited
            </Badge>
          )}

          {actionRow}
        </div>

        <MessageAvatar isUser user={user} />
      </article>
    )
  }

  return (
    <article
      id={`message-${message.id}`}
      // `group` drives the hover-reveal of the action row on pointer devices;
      // focus-within keeps it reachable by keyboard.
      className="group flex w-full animate-message-in gap-3 px-4 py-5 sm:px-6"
      aria-label="Assistant response"
    >
      <BrandMark size="sm" className="mt-0.5" />

      <div className="min-w-0 flex-1">
        <header className="mb-1 flex items-center gap-2">
          <h3 className="text-sm font-semibold">Assistant</h3>

          {message.model && (
            <span className="truncate rounded-md border bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              {message.model}
            </span>
          )}

          {isViewingOlder && (
            <Badge variant="outline" className="font-normal">
              older version
            </Badge>
          )}
        </header>

        {displayed ? (
          <CitationProvider value={citations}>
            <Markdown
              content={displayed}
              streaming={isStreaming}
              className={cn(isStreaming && 'streaming-caret')}
            />
          </CitationProvider>
        ) : (
          isStreaming && <ThinkingIndicator />
        )}

        {sources.length > 0 && (
          <MessageSources
            sources={sources}
            idPrefix={sourceIdPrefix}
            open={sourcesOpen}
            onOpenChange={setSourcesOpen}
            active={activeSource}
          />
        )}

        {message.error && (
          <AnswerFailed
            error={message.error}
            partial={Boolean(displayed)}
            disabled={isBusy || readOnly}
            {...(onRegenerate && !readOnly ? { onRetry: () => onRegenerate(message.id) } : {})}
            {...(onDelete && !readOnly ? { onRemove: () => onDelete(message.id) } : {})}
          />
        )}

        {message.truncated && !message.error && displayed && (
          <p className="mt-2 text-xs text-muted-foreground">
            Response stopped early.
          </p>
        )}

        {actionRow}
      </div>
    </article>
  )
})

/**
 * One place for a failed answer: what happened, that the question is safe,
 * and the two ways forward. The stream hook no longer raises a toast as well.
 */
function AnswerFailed({
  error,
  partial,
  disabled,
  onRetry,
  onRemove,
}: {
  error: string
  partial: boolean
  disabled: boolean
  onRetry?: () => void
  onRemove?: () => void
}) {
  const reason = /[.!?]$/.test(error) ? error : `${error}.`

  return (
    <div
      role="alert"
      className="mt-3 flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/[0.05] px-4 py-3"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">
          {partial ? 'The answer stopped partway' : 'No answer was generated'}
        </p>
        <p className="mt-0.5 break-words text-sm text-muted-foreground">
          {reason} Your question is saved, so you can retry once the service is back.
        </p>

        {(onRetry || onRemove) && (
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            {onRetry && (
              <Button size="sm" variant="outline" onClick={onRetry} disabled={disabled}>
                <RefreshCw />
                Retry
              </Button>
            )}
            {onRemove && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onRemove}
                disabled={disabled}
                className="text-muted-foreground hover:text-foreground"
              >
                <Trash2 />
                Remove answer
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function MessageAvatar({
  isUser,
  user,
}: {
  isUser: boolean
  user?: { name: string | null; image: string | null; email: string | null }
}) {
  if (!isUser) return <BrandMark size="sm" />

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
    <div className="flex items-center gap-2 py-1" role="status">
      <span className="text-shimmer text-sm font-medium">Thinking</span>
      <span className="flex gap-1" aria-hidden="true">
        {[0, 160, 320].map((delay) => (
          <span
            key={delay}
            className="size-1 animate-bounce rounded-full bg-muted-foreground"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
    </div>
  )
}
