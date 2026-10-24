'use client'

import { CheckCircle2, FileUp, Loader2, XCircle } from 'lucide-react'
import * as React from 'react'

import { Panel } from '@/components/admin/page-header'
import { StatusLabel } from '@/components/admin/status'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useAdminDocuments,
  useClearCache,
  useClearDocuments,
  useUploadDocument,
} from '@/hooks/use-admin'
import { LIMITS } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { CheckStatus, StoreStatus } from '@/types/admin'

const STORE_STATUS: Record<StoreStatus, CheckStatus> = {
  connected: 'ok',
  offline: 'degraded',
  unreachable: 'down',
}

const CONFIRM_WORD = 'clear'

interface QueuedFile {
  id: string
  file: File
  state: 'waiting' | 'indexing' | 'done' | 'failed'
  detail?: string
}

function UploadCard() {
  const upload = useUploadDocument()
  const [queue, setQueue] = React.useState<QueuedFile[]>([])
  const [dragging, setDragging] = React.useState(false)
  const busy = queue.some((item) => item.state === 'waiting' || item.state === 'indexing')

  const update = (id: string, patch: Partial<QueuedFile>) =>
    setQueue((items) => items.map((item) => (item.id === id ? { ...item, ...patch } : item)))

  // One at a time: the rag-service embeds every chunk on this machine.
  const start = async (files: File[]) => {
    const items = files.map((file) => ({
      id: `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`,
      file,
      state: 'waiting' as const,
    }))
    setQueue((current) => [...items, ...current.filter((item) => item.state !== 'done')])
    for (const item of items) {
      if (item.file.size > LIMITS.uploadBytes) {
        update(item.id, { state: 'failed', detail: 'Larger than 64 MB' })
        continue
      }
      update(item.id, { state: 'indexing' })
      try {
        const result = await upload.mutateAsync(item.file)
        update(item.id, { state: 'done', detail: `${result.chunks} chunks` })
      } catch (error) {
        update(item.id, { state: 'failed', detail: (error as Error).message })
      }
    }
  }

  const pick = (list: FileList | null) => {
    const files = Array.from(list ?? []).filter(
      (file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'),
    )
    if (files.length) void start(files)
  }

  return (
    <Panel
      title="Add documents"
      description="PDFs only, up to 64 MB each. Text comes from the PDF's text layer; scanned pages add nothing."
    >
      <div className="space-y-3 p-4">
        <label
          htmlFor="admin-upload"
          onDragOver={(event) => {
            event.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            pick(event.dataTransfer.files)
          }}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors',
            dragging ? 'border-primary bg-primary/5' : 'hover:bg-accent/50',
          )}
        >
          <FileUp className="size-6 text-muted-foreground" />
          <span className="text-sm font-medium">Drop PDFs here or choose files</span>
          <span className="text-xs text-muted-foreground">
            Every user&apos;s answers can draw on them. Cached answers are cleared after each one.
          </span>
          <input
            id="admin-upload"
            type="file"
            accept="application/pdf,.pdf"
            multiple
            className="sr-only"
            onChange={(event) => {
              pick(event.target.files)
              event.target.value = ''
            }}
          />
        </label>

        {queue.length > 0 && (
          <ul className="divide-y rounded-lg border" aria-live="polite">
            {queue.map((item) => (
              <li key={item.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                {item.state === 'done' ? (
                  <CheckCircle2 className="size-4 shrink-0 text-emerald-600" aria-hidden="true" />
                ) : item.state === 'failed' ? (
                  <XCircle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
                ) : (
                  <Loader2
                    className={cn(
                      'size-4 shrink-0 text-muted-foreground',
                      item.state === 'indexing' && 'animate-spin',
                    )}
                    aria-hidden="true"
                  />
                )}
                <span className="min-w-0 flex-1 truncate">{item.file.name}</span>
                <span
                  className={cn(
                    'shrink-0 text-xs',
                    item.state === 'failed' ? 'text-destructive' : 'text-muted-foreground',
                  )}
                >
                  {item.state === 'waiting'
                    ? 'Waiting'
                    : item.state === 'indexing'
                      ? 'Indexing…'
                      : item.state === 'done'
                        ? `Indexed · ${item.detail}`
                        : item.detail}
                </span>
              </li>
            ))}
          </ul>
        )}
        {busy && (
          <p className="text-xs text-muted-foreground">
            Large files can take a few minutes: every chunk is embedded on this machine.
          </p>
        )}
      </div>
    </Panel>
  )
}

function ClearIndexDialog({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}) {
  const [typed, setTyped] = React.useState('')

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setTyped('')
        onOpenChange(next)
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Remove every document?</AlertDialogTitle>
          <AlertDialogDescription>
            This empties the index for every user, and clears cached answers. Answers go back to
            general knowledge until documents are uploaded again. It cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="confirm-clear">
            Type <span className="font-mono font-semibold">{CONFIRM_WORD}</span> to confirm
          </Label>
          <Input
            id="confirm-clear"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            autoComplete="off"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={typed.trim().toLowerCase() !== CONFIRM_WORD}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={onConfirm}
          >
            Remove every document
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function DocumentsPanel() {
  const stats = useAdminDocuments()
  const clearCache = useClearCache()
  const clearIndex = useClearDocuments()
  const [confirmClear, setConfirmClear] = React.useState(false)
  const data = stats.data

  return (
    <div className="space-y-6">
      <dl className="grid gap-3 sm:grid-cols-2">
        {data ? (
          <>
            <div className="rounded-lg border bg-card p-4">
              <div className="flex items-center justify-between gap-2">
                <dt className="text-xs font-medium text-muted-foreground">Indexed chunks</dt>
                <StatusLabel status={STORE_STATUS[data.index.status]} />
              </div>
              <dd className="mt-1.5 text-2xl font-semibold tabular-nums">
                {data.index.chunks ?? '—'}
              </dd>
              <dd className="mt-0.5 text-xs text-muted-foreground">
                One shared index; every user&apos;s answers draw on it.
              </dd>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <div className="flex items-center justify-between gap-2">
                <dt className="text-xs font-medium text-muted-foreground">Cached answers</dt>
                <StatusLabel status={STORE_STATUS[data.cache.status]} />
              </div>
              <dd className="mt-1.5 text-2xl font-semibold tabular-nums">
                {data.cache.answers ?? '—'}
              </dd>
              <dd className="mt-0.5 text-xs text-muted-foreground">
                Kept for an hour per question and model.
              </dd>
            </div>
          </>
        ) : stats.isError ? (
          <p role="alert" className="text-sm text-destructive">
            Could not read the index: {stats.error.message}
          </p>
        ) : (
          <>
            <Skeleton className="h-[6.5rem] rounded-lg" />
            <Skeleton className="h-[6.5rem] rounded-lg" />
          </>
        )}
      </dl>

      <UploadCard />

      <Panel title="Danger zone" className="border-destructive/40">
        <ul className="divide-y">
          <li className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium">Clear cached answers</p>
              <p className="text-xs text-muted-foreground">
                Repeated questions are answered fresh. Documents are not touched.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => clearCache.mutate()}
              disabled={clearCache.isPending}
            >
              {clearCache.isPending && <Loader2 className="animate-spin" />}
              Clear cache
            </Button>
          </li>
          <li className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium">Remove every document</p>
              <p className="text-xs text-muted-foreground">
                Empties the shared index for every user. There is no way to remove a single
                document yet.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => setConfirmClear(true)}
              disabled={clearIndex.isPending}
            >
              {clearIndex.isPending && <Loader2 className="animate-spin" />}
              Clear index
            </Button>
          </li>
        </ul>
      </Panel>

      <ClearIndexDialog
        open={confirmClear}
        onOpenChange={setConfirmClear}
        onConfirm={() => clearIndex.mutate()}
      />
    </div>
  )
}
