import { NextResponse } from 'next/server'

import { requireAdmin, withErrorHandling } from '@/server/http'
import { clearAnswerCache } from '@/server/services/admin-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export const POST = withErrorHandling(async () => {
  const admin = await requireAdmin()
  return NextResponse.json({ data: { cleared: await clearAnswerCache(admin.id) } })
})
