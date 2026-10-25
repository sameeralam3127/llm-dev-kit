import { NextResponse } from 'next/server'

import { requireAdmin, withErrorHandling } from '@/server/http'
import { listAllApiKeys } from '@/server/services/admin-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export const GET = withErrorHandling(async () => {
  await requireAdmin()
  return NextResponse.json({ data: await listAllApiKeys() })
})
