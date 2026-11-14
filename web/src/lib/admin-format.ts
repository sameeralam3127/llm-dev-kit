import { plural } from '@/lib/utils'
import type { AuditEventDTO, IngestionStatus } from '@/types/admin'

/** `1.5 MB`, `812 B`: sizes the way people read them. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value >= 10 ? Math.round(value) : Math.round(value * 10) / 10} ${units[unit]}`
}

/** `850 ms`, `12 s`, `2 min 5 s`: how long something took. */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))} ms`
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return rest ? `${minutes} min ${rest} s` : `${minutes} min`
}

export const AUDIT_ACTION_LABELS: Record<string, string> = {
  'user.role_changed': 'Changed a role',
  'api_key.revoked': 'Revoked an API key',
  'document.uploaded': 'Uploaded a document',
  'document.upload_failed': 'Upload failed',
  'document.index_cleared': 'Cleared the document index',
  'cache.cleared': 'Cleared cached answers',
}

/** The filter options of the audit viewer: an action family and its label. */
export const AUDIT_FILTERS = [
  { prefix: '', label: 'Everything' },
  { prefix: 'user.', label: 'People' },
  { prefix: 'api_key.', label: 'API keys' },
  { prefix: 'document.', label: 'Documents' },
  { prefix: 'cache.', label: 'Cache' },
] as const

const text = (value: unknown): string => (typeof value === 'string' ? value : '')
const num = (value: unknown): number => (typeof value === 'number' ? value : 0)

/** One readable line for an entry's details. Unknown actions fall back to `key: value` pairs. */
export function describeAudit(event: Pick<AuditEventDTO, 'action' | 'detail'>): string {
  // Nothing recorded, nothing to say: no stray punctuation from empty fields.
  if (!event.detail) return ''
  const d = event.detail
  switch (event.action) {
    case 'user.role_changed':
      return `${text(d['email'])}: ${text(d['from'])} → ${text(d['to'])}`
    case 'api_key.revoked':
      return `${text(d['name'])} (${text(d['prefix'])}…), owned by ${text(d['owner'])}`
    case 'document.uploaded':
      return `${plural(num(d['chunks']), 'chunk')}, ${formatBytes(num(d['bytes']))}`
    case 'document.upload_failed':
      return text(d['error'])
    case 'document.index_cleared':
      return typeof d['cacheCleared'] === 'number'
        ? `${plural(d['cacheCleared'], 'cached answer')} dropped too`
        : 'Cached answers could not be cleared'
    case 'cache.cleared':
      return plural(num(d['cleared']), 'cached answer')
    default:
      return Object.entries(d)
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join(', ')
  }
}

export const INGESTION_STATUS_LABELS: Record<IngestionStatus, string> = {
  running: 'Indexing',
  succeeded: 'Indexed',
  failed: 'Failed',
  interrupted: 'Interrupted',
}
