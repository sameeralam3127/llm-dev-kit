'use client'

import { formatDistanceToNow } from 'date-fns'
import { Loader2 } from 'lucide-react'

import { Panel } from '@/components/admin/page-header'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useIngestionJobs } from '@/hooks/use-admin'
import { formatBytes, formatDuration, INGESTION_STATUS_LABELS } from '@/lib/admin-format'

export function IngestionJobsPanel() {
  const jobs = useIngestionJobs()

  return (
    <Panel
      title="Recent uploads"
      description="Uploads made from this console, with how each one went. Files sent straight to the API (curl) bypass the console and are not listed."
    >
      {jobs.isLoading ? (
        <div className="space-y-2 p-4">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
        </div>
      ) : jobs.isError ? (
        <p role="alert" className="px-4 py-3 text-sm text-destructive">
          Could not load uploads: {jobs.error.message}
        </p>
      ) : jobs.data?.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">No uploads yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Recent uploads</caption>
            <thead className="border-b text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-medium">File</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                <th scope="col" className="px-4 py-2.5 text-right font-medium">Chunks</th>
                <th scope="col" className="px-4 py-2.5 text-right font-medium">Took</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {jobs.data?.map((job) => (
                <tr key={job.id}>
                  <th scope="row" className="max-w-[18rem] px-4 py-2.5 font-medium">
                    <span className="block truncate">{job.filename}</span>
                    <span className="block text-xs font-normal text-muted-foreground">
                      {formatBytes(job.sizeBytes)}
                      {job.uploadedBy ? ` · ${job.uploadedBy}` : ''}
                    </span>
                    {job.error && (
                      <span className="mt-0.5 block text-xs font-normal text-destructive">{job.error}</span>
                    )}
                  </th>
                  <td className="px-4 py-2.5">
                    <Badge
                      variant={job.status === 'failed' ? 'destructive' : job.status === 'succeeded' ? 'outline' : 'secondary'}
                      className="gap-1 font-normal"
                    >
                      {job.status === 'running' && <Loader2 className="size-3 animate-spin" aria-hidden="true" />}
                      {INGESTION_STATUS_LABELS[job.status]}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{job.chunks ?? '—'}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-right tabular-nums text-muted-foreground">
                    {job.finishedAt
                      ? formatDuration(new Date(job.finishedAt).getTime() - new Date(job.startedAt).getTime())
                      : '—'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                    {formatDistanceToNow(new Date(job.startedAt), { addSuffix: true })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}
