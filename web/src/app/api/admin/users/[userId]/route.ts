import { NextResponse } from 'next/server'

import { updateUserSchema } from '@/lib/validations/admin'
import { parseBody, requireAdmin, withErrorHandling } from '@/server/http'
import { setUserRole } from '@/server/services/admin-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type RouteContext = { params: Promise<{ userId: string }> }

export const PATCH = withErrorHandling(async (request: Request, context: RouteContext) => {
  const admin = await requireAdmin()
  const { userId } = await context.params
  const { role } = await parseBody(request, updateUserSchema)
  return NextResponse.json({ data: await setUserRole(admin, userId, role) })
})
