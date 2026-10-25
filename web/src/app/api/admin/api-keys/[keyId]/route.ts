import { NextResponse } from 'next/server'

import { requireAdmin, withErrorHandling } from '@/server/http'
import { revokeAnyApiKey } from '@/server/services/admin-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type RouteContext = { params: Promise<{ keyId: string }> }

export const DELETE = withErrorHandling(async (_request: Request, context: RouteContext) => {
  await requireAdmin()
  const { keyId } = await context.params
  await revokeAnyApiKey(keyId)
  return new NextResponse(null, { status: 204 })
})
