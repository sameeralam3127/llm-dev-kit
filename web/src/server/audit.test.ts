// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from 'vitest'

interface Row {
  id: string
  at: Date
  actorId: string | null
  actorEmail: string | null
  action: string
  target: string | null
  detail: string | null
}

const state = vi.hoisted(() => ({ rows: [] as Row[], sql: [] as string[], postgres: false }))

vi.mock('@/lib/db', () => ({
  db: {
    auditEvent: {
      create: async ({ data }: { data: Omit<Row, 'id' | 'at'> }) => {
        state.rows.push({ id: `evt${String(state.rows.length).padStart(10, '0')}`, at: new Date(1_000 + state.rows.length), ...data })
      },
      // Newest first, with the cursor and prefix handling Prisma would do.
      findMany: async (args: {
        where: { action?: { startsWith: string } }
        take: number
        cursor?: { id: string }
        skip?: number
      }) => {
        let rows = [...state.rows].reverse()
        if (args.where.action) rows = rows.filter((r) => r.action.startsWith(args.where.action!.startsWith))
        if (args.cursor) rows = rows.slice(rows.findIndex((r) => r.id === args.cursor!.id) + (args.skip ?? 0))
        return rows.slice(0, args.take)
      },
    },
    $executeRawUnsafe: async (sql: string) => void state.sql.push(sql),
  },
}))

vi.mock('@/lib/db-kind', () => ({ isPostgres: () => state.postgres }))

import { ensureAuditTriggers, listAuditEvents, recordAudit } from '@/server/audit'

const ACTOR = { id: 'u1', email: 'admin@example.test' }

beforeEach(() => {
  state.rows = []
  state.sql = []
  state.postgres = false
})

describe('recordAudit', () => {
  it('stores the actor as a snapshot and the detail as JSON text', async () => {
    await recordAudit(ACTOR, { action: 'cache.cleared', detail: { cleared: 2 } })
    expect(state.rows[0]).toMatchObject({
      actorId: 'u1',
      actorEmail: 'admin@example.test',
      action: 'cache.cleared',
      target: null,
      detail: '{"cleared":2}',
    })
  })
})

describe('listAuditEvents', () => {
  const seed = async (n: number) => {
    for (let i = 0; i < n; i++) {
      await recordAudit(ACTOR, { action: i % 2 ? 'user.role_changed' : 'cache.cleared', detail: { i } })
    }
  }

  it('pages newest first without gaps or repeats, then reports the end', async () => {
    await seed(5)
    const first = await listAuditEvents({ limit: 2 })
    expect(first.events.map((e) => e.detail?.['i'])).toEqual([4, 3])
    expect(first.nextBefore).toBe(first.events[1]!.id)

    const second = await listAuditEvents({ limit: 2, before: first.nextBefore! })
    expect(second.events.map((e) => e.detail?.['i'])).toEqual([2, 1])

    const last = await listAuditEvents({ limit: 2, before: second.nextBefore! })
    expect(last.events.map((e) => e.detail?.['i'])).toEqual([0])
    expect(last.nextBefore).toBeNull()
  })

  it('keeps one family of actions', async () => {
    await seed(4)
    const page = await listAuditEvents({ prefix: 'user.' })
    expect(page.events.map((e) => e.action)).toEqual(['user.role_changed', 'user.role_changed'])
  })

  it('survives an entry whose detail is not valid JSON', async () => {
    state.rows.push({ id: 'bad0000000', at: new Date(), actorId: null, actorEmail: null, action: 'x.y', target: null, detail: '{oops' })
    expect((await listAuditEvents({})).events[0]!.detail).toBeNull()
  })

  it('exposes only the byte count and a safe code for older failed uploads', async () => {
    state.rows.push({
      id: 'legacy-upload',
      at: new Date(),
      actorId: null,
      actorEmail: null,
      action: 'document.upload_failed',
      target: 'scan.pdf',
      detail: JSON.stringify({ bytes: 21, error: 'Synthetic older audit diagnostic' }),
    })
    expect((await listAuditEvents({})).events[0]?.detail).toEqual({
      bytes: 21,
      errorCode: 'upstream_error',
    })
  })
})

describe('ensureAuditTriggers', () => {
  it('forbids both UPDATE and DELETE on the table', async () => {
    await ensureAuditTriggers()
    expect(state.sql).toHaveLength(2)
    expect(state.sql.join('\n')).toMatch(/BEFORE UPDATE ON "AuditEvent"[\s\S]*RAISE\(ABORT/)
    expect(state.sql.join('\n')).toMatch(/BEFORE DELETE ON "AuditEvent"[\s\S]*RAISE\(ABORT/)
    expect(state.sql.every((sql) => sql.includes('IF NOT EXISTS'))).toBe(true)
  })

  it('uses a plpgsql trigger function on Postgres, re-runnable at every start', async () => {
    state.postgres = true
    await ensureAuditTriggers()
    const sql = state.sql.join('\n')
    expect(sql).toMatch(/CREATE OR REPLACE FUNCTION audit_event_append_only\(\)[\s\S]*RAISE EXCEPTION/)
    expect(sql).toMatch(/CREATE OR REPLACE TRIGGER audit_event_no_update BEFORE UPDATE ON "AuditEvent"/)
    expect(sql).toMatch(/CREATE OR REPLACE TRIGGER audit_event_no_delete BEFORE DELETE ON "AuditEvent"/)
    expect(sql).not.toMatch(/RAISE\(ABORT/)
  })
})
