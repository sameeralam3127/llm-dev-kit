'use client'

import { useServiceStatus } from '@/hooks/use-service-status'

/**
 * Shown only while answers cannot be generated. Silent the rest of the time:
 * a permanent green "online" badge is noise nobody reads.
 */
export function ServiceStatusNotice() {
  const { offline } = useServiceStatus()
  if (!offline) return null

  return (
    <span
      role="status"
      title="The model host isn't responding. Checked every 30 seconds."
      className="mr-1 inline-flex h-8 items-center gap-1.5 rounded-md border border-destructive/30 px-2 text-xs font-medium text-destructive"
    >
      <span className="size-1.5 rounded-full bg-destructive" aria-hidden="true" />
      <span className="sr-only sm:not-sr-only">Model host offline</span>
    </span>
  )
}
