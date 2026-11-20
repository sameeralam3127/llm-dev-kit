import 'server-only'

import type { Prisma } from '@prisma/client'

import { db } from '@/lib/db'
import type { AuditEventDTO } from '@/types/admin'

/** Who is acting. Snapshotted into the entry, so it survives account changes. */
export interface Actor {
  id: string
  email: string
}

export const AUDIT_ACTIONS = [
  'user.role_changed',
  'api_key.revoked',
  'document.uploaded',
  'document.upload_failed',
  'document.index_cleared',
  'cache.cleared',
] as const

export type AuditAction = (typeof AUDIT_ACTIONS)[number]

/** Anything with `auditEvent`, so a transaction can write its entry atomically. */
type AuditClient = Pick<Prisma.TransactionClient, 'auditEvent'>

export interface AuditInput {
  action: AuditAction
  /** What was acted on: `user:<id>`, `api_key:<id>`, a filename. */
  target?: string
  /** Names, counts and prefixes only. Never a key, token, password or file content. */
  detail?: Record<string, unknown>
}

/** Append one entry. Pass a transaction client to commit it with the change it describes. */
export async function recordAudit(
  actor: Actor,
  input: AuditInput,
  client: AuditClient = db,
): Promise<void> {
  await client.auditEvent.create({
    data: {
      actorId: actor.id,
      actorEmail: actor.email,
      action: input.action,
      target: input.target ?? null,
      detail: input.detail ? JSON.stringify(input.detail) : null,
    },
  })
}

export const AUDIT_PAGE_SIZE = 50

export interface AuditPage {
  events: AuditEventDTO[]
  /** Pass as `before` to get the next, older page; null when there is none. */
  nextBefore: string | null
}

/** Newest first. `prefix` keeps one family of actions, e.g. `user.` or `document.`. */
export async function listAuditEvents(params: {
  before?: string
  prefix?: string
  limit?: number
}): Promise<AuditPage> {
  const limit = Math.min(Math.max(params.limit ?? AUDIT_PAGE_SIZE, 1), 200)
  const rows = await db.auditEvent.findMany({
    where: params.prefix ? { action: { startsWith: params.prefix } } : {},
    orderBy: [{ at: 'desc' }, { id: 'desc' }],
    take: limit + 1,
    ...(params.before ? { cursor: { id: params.before }, skip: 1 } : {}),
  })
  const page = rows.slice(0, limit)
  return {
    events: page.map((row) => ({
      id: row.id,
      at: row.at.toISOString(),
      actorId: row.actorId,
      actorEmail: row.actorEmail,
      action: row.action,
      target: row.target,
      detail: parseDetail(row.detail),
    })),
    nextBefore: rows.length > limit ? (page.at(-1)?.id ?? null) : null,
  }
}

function parseDetail(text: string | null): Record<string, unknown> | null {
  if (!text) return null
  try {
    const parsed: unknown = JSON.parse(text)
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null
  } catch {
    return null
  }
}

/**
 * Make the table append-only in the database itself, so a bug elsewhere in the
 * app (or a stray query) cannot rewrite history. Prisma cannot express
 * triggers, and `db push` can recreate a table and drop them, so this runs at
 * every start, after the schema is pushed. Idempotent.
 *
 * This guards against bugs and stray queries. It does not stop someone who can
 * run arbitrary SQL on the database: they can drop the triggers. Moving the
 * log to Postgres in v3 with a separate role is the real fix (#55).
 */
export async function ensureAuditTriggers(): Promise<void> {
  for (const [name, event] of [
    ['audit_event_no_update', 'UPDATE'],
    ['audit_event_no_delete', 'DELETE'],
  ] as const) {
    await db.$executeRawUnsafe(
      `CREATE TRIGGER IF NOT EXISTS ${name} BEFORE ${event} ON "AuditEvent" ` +
        `BEGIN SELECT RAISE(ABORT, 'AuditEvent is append-only'); END`,
    )
  }
}
