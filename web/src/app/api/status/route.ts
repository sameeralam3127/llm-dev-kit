import { NextResponse } from 'next/server'

import { checkModelHost } from '@/lib/llm'
import { requireUser, withErrorHandling } from '@/server/http'
import type { ServiceStatus } from '@/types/chat'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export const GET = withErrorHandling(async () => {
  const user = await requireUser()
  const { online, checkedAt } = await checkModelHost(user.id)
  const data: ServiceStatus = { modelHost: online ? 'online' : 'offline', checkedAt }
  return NextResponse.json({ data })
})
