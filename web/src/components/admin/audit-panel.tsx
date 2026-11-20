'use client'

import { format } from 'date-fns'
import * as React from 'react'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useAuditLog } from '@/hooks/use-admin'
import { AUDIT_ACTION_LABELS, AUDIT_FILTERS, describeAudit } from '@/lib/admin-format'

export function AuditPanel() {
  const [prefix, setPrefix] = React.useState('')
  const log = useAuditLog(prefix)
  const events = log.data?.pages.flatMap((page) => page.events) ?? []

  return (
    <section aria-label="Audit log" className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <Select value={prefix || 'all'} onValueChange={(value) => setPrefix(value === 'all' ? '' : value)}>
          <SelectTrigger className="sm:w-44" aria-label="Filter by kind of action">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AUDIT_FILTERS.map((filter) => (
              <SelectItem key={filter.prefix || 'all'} value={filter.prefix || 'all'}>
                {filter.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {log.data && (
          <p className="text-xs text-muted-foreground sm:ml-auto">
            {events.length} {events.length === 1 ? 'entry' : 'entries'} shown, newest first
          </p>
        )}
      </div>

      {log.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading the audit log…</p>
      ) : log.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Could not load the audit log: {log.error.message}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">When</th>
                <th scope="col" className="px-3 py-2 font-medium">Who</th>
                <th scope="col" className="px-3 py-2 font-medium">Action</th>
                <th scope="col" className="px-3 py-2 font-medium">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {events.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-sm text-muted-foreground">
                    Nothing recorded yet. Role changes, key revocations, uploads and clears appear here.
                  </td>
                </tr>
              )}
              {events.map((event) => (
                <tr key={event.id}>
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">
                    <time dateTime={event.at}>{format(new Date(event.at), 'd MMM yyyy, HH:mm:ss')}</time>
                  </td>
                  <td className="px-3 py-2.5">{event.actorEmail ?? 'Unknown'}</td>
                  <td className="px-3 py-2.5">
                    <p className="font-medium">{AUDIT_ACTION_LABELS[event.action] ?? event.action}</p>
                    {event.target && (
                      <p className="max-w-[16rem] truncate font-mono text-xs text-muted-foreground">
                        {event.target}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{describeAudit(event)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {log.hasNextPage && (
        <div className="flex justify-center">
          <Button variant="outline" size="sm" onClick={() => void log.fetchNextPage()} disabled={log.isFetchingNextPage}>
            {log.isFetchingNextPage ? 'Loading…' : 'Load older entries'}
          </Button>
        </div>
      )}
    </section>
  )
}
