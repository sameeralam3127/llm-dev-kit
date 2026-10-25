'use client'

import { formatDistanceToNow } from 'date-fns'
import { ArrowRight } from 'lucide-react'
import Link from 'next/link'
import type * as React from 'react'

import { ActivityChart } from '@/components/admin/activity-chart'
import { Panel } from '@/components/admin/page-header'
import { overallStatus, STATUS, StatusLabel } from '@/components/admin/status'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminHealth, useAdminOverview } from '@/hooks/use-admin'
import { ROUTES } from '@/lib/constants'
import type { CheckStatus } from '@/types/admin'

function Stat({ label, value, hint }: { label: string; value: number | string | null; hint?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight">
        {value ?? '—'}
      </dd>
      {hint && <dd className="mt-0.5 text-xs text-muted-foreground">{hint}</dd>}
    </div>
  )
}

function SectionLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
    >
      {children}
      <ArrowRight className="size-3" />
    </Link>
  )
}

/** "6 OK · 1 off": a service that is switched off is not a problem. */
function serviceSummary(statuses: CheckStatus[]): string {
  const count = (status: CheckStatus) => statuses.filter((s) => s === status).length
  return (['ok', 'degraded', 'down', 'off'] as const)
    .filter((status) => count(status) > 0)
    .map((status) => `${count(status)} ${status === 'ok' ? 'OK' : STATUS[status].label.toLowerCase()}`)
    .join(' · ')
}

export function OverviewPanel() {
  const overview = useAdminOverview()
  const health = useAdminHealth()
  const counts = overview.data?.counts
  const checks = health.data?.checks ?? []
  const overall = checks.length ? overallStatus(checks.map((c) => c.status)) : null
  const questions = overview.data?.activity.reduce((sum, day) => sum + day.messages, 0) ?? 0

  if (overview.isError) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Could not load the overview: {overview.error.message}
      </p>
    )
  }

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {counts ? (
          <>
            <Stat label="Users" value={counts.users} hint={`${counts.admins} admin${counts.admins === 1 ? '' : 's'}`} />
            <Stat label="Chats" value={counts.chats} hint={`${counts.sharedChats} shared`} />
            <Stat label="Messages" value={counts.messages} />
            <Stat label="Active API keys" value={counts.apiKeys} />
            <Stat label="Indexed chunks" value={health.data?.counts.indexedChunks ?? null} />
            <Stat
              label="Services"
              value={overall ? STATUS[overall].label : null}
              hint={overall ? serviceSummary(checks.map((c) => c.status)) : 'Checking…'}
            />
          </>
        ) : (
          Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-[6.25rem] rounded-lg" />)
        )}
      </dl>

      <div className="grid gap-6 lg:grid-cols-3">
        <Panel
          title="Questions per day"
          description={
            overview.data ? `${questions} in the last 14 days` : 'The last 14 days'
          }
          className="lg:col-span-2"
        >
          <div className="px-4 pb-4 pt-6">
            {overview.data ? (
              <ActivityChart days={overview.data.activity} />
            ) : (
              <Skeleton className="h-[11rem] w-full" />
            )}
          </div>
        </Panel>

        <Panel
          title="Services"
          description="Checked from the web app every 30 seconds"
          actions={<SectionLink href={ROUTES.adminSystem}>Details</SectionLink>}
        >
          {health.isError ? (
            <p role="alert" className="px-4 py-3 text-sm text-destructive">
              Could not run the checks: {health.error.message}
            </p>
          ) : (
            <ul className="divide-y">
              {(checks.length ? checks : Array.from({ length: 5 }, () => null)).map((check, i) =>
                check ? (
                  <li key={check.name} className="flex items-center justify-between gap-3 px-4 py-2.5">
                    <span className="truncate text-sm">{check.name}</span>
                    <StatusLabel status={check.status} />
                  </li>
                ) : (
                  <li key={i} className="px-4 py-2.5">
                    <Skeleton className="h-4 w-full" />
                  </li>
                ),
              )}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title="Newest accounts"
        actions={<SectionLink href={ROUTES.adminUsers}>All users</SectionLink>}
      >
        <ul className="divide-y">
          {overview.data
            ? overview.data.recentUsers.map((user) => (
                <li key={user.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{user.name ?? user.email}</p>
                    {user.name && (
                      <p className="truncate text-xs text-muted-foreground">{user.email}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <Badge variant="secondary" className="font-normal">
                      {user.role}
                    </Badge>
                    <span className="hidden text-xs text-muted-foreground sm:inline">
                      Joined {formatDistanceToNow(new Date(user.createdAt), { addSuffix: true })}
                    </span>
                  </div>
                </li>
              ))
            : Array.from({ length: 3 }, (_, i) => (
                <li key={i} className="px-4 py-3">
                  <Skeleton className="h-4 w-1/2" />
                </li>
              ))}
        </ul>
      </Panel>
    </div>
  )
}
