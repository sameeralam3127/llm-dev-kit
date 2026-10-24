import { NextResponse } from 'next/server'

import { requireAdmin, withErrorHandling } from '@/server/http'
import { clearDocumentIndex } from '@/server/services/admin-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export const POST = withErrorHandling(async () => {
  const admin = await requireAdmin()
  return NextResponse.json({ data: await clearDocumentIndex(admin.id) })
})
