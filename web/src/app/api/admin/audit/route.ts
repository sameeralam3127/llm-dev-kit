import { NextResponse } from 'next/server'

import { AUDIT_ACTIONS, listAuditEvents } from '@/server/audit'
import { badRequest, requireAdmin, withErrorHandling } from '@/server/http'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/** The family prefixes the viewer filters by: `user.`, `api_key.`, `document.`, `cache.`. */
const PREFIXES = new Set(AUDIT_ACTIONS.map((action) => `${action.split('.')[0]}.`))

export const GET = withErrorHandling(async (request: Request) => {
  await requireAdmin()
  const params = new URL(request.url).searchParams
  const prefix = params.get('prefix') ?? undefined
  if (prefix !== undefined && !PREFIXES.has(prefix)) throw badRequest('Unknown action filter')
  const before = params.get('before') ?? undefined
  if (before !== undefined && !/^[a-z0-9]{10,40}$/.test(before)) throw badRequest('Invalid page cursor')
  return NextResponse.json({ data: await listAuditEvents({ prefix, before }) })
})
