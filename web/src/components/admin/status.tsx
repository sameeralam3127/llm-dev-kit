import { cn } from '@/lib/utils'
import type { CheckStatus } from '@/types/admin'

export const STATUS: Record<CheckStatus, { label: string; dot: string }> = {
  ok: { label: 'OK', dot: 'bg-emerald-500' },
  degraded: { label: 'Degraded', dot: 'bg-amber-500' },
  down: { label: 'Down', dot: 'bg-red-500' },
  off: { label: 'Off', dot: 'bg-muted-foreground/40' },
}

/** A status dot that always comes with its label, so it never relies on colour alone. */
export function StatusLabel({
  status,
  label,
  className,
}: {
  status: CheckStatus
  /** Replaces the status's own word, e.g. "On" for a setting. */
  label?: string
  className?: string
}) {
  return (
    <span className={cn('flex items-center gap-1.5 text-xs text-muted-foreground', className)}>
      <span aria-hidden="true" className={cn('size-2 rounded-full', STATUS[status].dot)} />
      {label ?? STATUS[status].label}
    </span>
  )
}

/** The worst status among `statuses`, for a one-word summary. */
export function overallStatus(statuses: CheckStatus[]): CheckStatus {
  if (statuses.includes('down')) return 'down'
  if (statuses.includes('degraded')) return 'degraded'
  return 'ok'
}
