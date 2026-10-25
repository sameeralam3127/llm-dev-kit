'use client'

import { formatDistanceToNow } from 'date-fns'
import { RefreshCw } from 'lucide-react'

import { Panel } from '@/components/admin/page-header'
import { StatusLabel } from '@/components/admin/status'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminHealth } from '@/hooks/use-admin'
import { cn } from '@/lib/utils'

export function HealthPanel() {
  const health = useAdminHealth()
  const data = health.data

  return (
    <Panel
      title="Services"
      description={
        data
          ? `Checked ${formatDistanceToNow(new Date(data.checkedAt), { addSuffix: true })}; refreshes every 30 seconds.`
          : 'Each service, checked from the web app.'
      }
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={() => void health.refetch()}
          disabled={health.isFetching}
          className="gap-1.5"
        >
          <RefreshCw className={cn('size-3.5', health.isFetching && 'animate-spin')} />
          Check now
        </Button>
      }
    >
      {health.isError ? (
        <p role="alert" className="px-4 py-3 text-sm text-destructive">
          Could not run the checks: {health.error.message}
        </p>
      ) : (
        <ul className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
          {data
            ? data.checks.map((check) => (
                <li key={check.name} className="rounded-md border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{check.name}</span>
                    <StatusLabel status={check.status} />
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{check.detail}</p>
                </li>
              ))
            : Array.from({ length: 6 }, (_, i) => (
                <li key={i} className="rounded-md border p-3">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="mt-2 h-3 w-full" />
                </li>
              ))}
        </ul>
      )}
    </Panel>
  )
}
