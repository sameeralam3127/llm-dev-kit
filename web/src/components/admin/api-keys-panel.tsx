'use client'

import { format, formatDistanceToNow } from 'date-fns'
import { Search } from 'lucide-react'
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
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useAdminApiKeys, useRevokeAnyApiKey } from '@/hooks/use-admin'
import type { AdminApiKey } from '@/types/admin'

type StateFilter = 'active' | 'revoked' | 'all'

export function AdminApiKeysPanel() {
  const keys = useAdminApiKeys()
  const revoke = useRevokeAnyApiKey()
  const [query, setQuery] = React.useState('')
  const [state, setState] = React.useState<StateFilter>('active')
  const [confirming, setConfirming] = React.useState<AdminApiKey | null>(null)

  const needle = query.trim().toLowerCase()
  const all = keys.data ?? []
  const shown = all.filter(
    (key) =>
      (state === 'all' || (state === 'active') === (key.revokedAt === null)) &&
      (!needle ||
        key.name.toLowerCase().includes(needle) ||
        key.prefix.toLowerCase().includes(needle) ||
        key.owner.email.toLowerCase().includes(needle) ||
        (key.owner.name ?? '').toLowerCase().includes(needle)),
  )

  return (
    <section aria-label="API keys" className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative sm:w-72">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by key, prefix or owner"
            aria-label="Search API keys"
            className="pl-8"
          />
        </div>
        <Select value={state} onValueChange={(value) => setState(value as StateFilter)}>
          <SelectTrigger className="sm:w-36" aria-label="Filter by state">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="revoked">Revoked</SelectItem>
            <SelectItem value="all">All keys</SelectItem>
          </SelectContent>
        </Select>
        {keys.data && (
          <p className="text-xs text-muted-foreground sm:ml-auto">
            {all.filter((key) => !key.revokedAt).length} active of {all.length}
          </p>
        )}
      </div>

      {keys.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading keys…</p>
      ) : keys.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Could not load API keys: {keys.error.message}
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Key</th>
                <th scope="col" className="px-3 py-2 font-medium">Owner</th>
                <th scope="col" className="px-3 py-2 font-medium">Created</th>
                <th scope="col" className="px-3 py-2 font-medium">Last used</th>
                <th scope="col" className="px-3 py-2 font-medium">State</th>
                <th scope="col" className="px-3 py-2">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {shown.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-sm text-muted-foreground">
                    {all.length === 0 ? 'Nobody has created an API key yet.' : 'No keys match.'}
                  </td>
                </tr>
              )}
              {shown.map((key) => (
                <tr key={key.id}>
                  <td className="px-3 py-2.5">
                    <p className="font-medium">{key.name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{key.prefix}…</p>
                  </td>
                  <td className="px-3 py-2.5">
                    <p>{key.owner.name ?? key.owner.email}</p>
                    {key.owner.name && (
                      <p className="text-xs text-muted-foreground">{key.owner.email}</p>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">
                    {format(new Date(key.createdAt), 'd MMM yyyy')}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">
                    {key.lastUsedAt
                      ? formatDistanceToNow(new Date(key.lastUsedAt), { addSuffix: true })
                      : 'Never'}
                  </td>
                  <td className="px-3 py-2.5">
                    {key.revokedAt ? (
                      <Badge variant="secondary" className="font-normal">
                        Revoked {format(new Date(key.revokedAt), 'd MMM')}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="font-normal">
                        Active
                      </Badge>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {!key.revokedAt && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setConfirming(key)}
                      >
                        Revoke
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AlertDialog open={confirming !== null} onOpenChange={(open) => !open && setConfirming(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke “{confirming?.name}”?</AlertDialogTitle>
            <AlertDialogDescription>
              Anything using this key for {confirming?.owner.name ?? confirming?.owner.email} stops
              working within a minute. This cannot be undone; they can create a new key.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => confirming && revoke.mutate({ id: confirming.id, name: confirming.name })}
            >
              Revoke key
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
