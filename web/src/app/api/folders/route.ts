import { NextResponse } from 'next/server'

import { createFolderSchema } from '@/lib/validations/chat'
import { parseBody, requireUser, withErrorHandling } from '@/server/http'
import { createFolder, listFolders } from '@/server/services/folder-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export const GET = withErrorHandling(async () => {
  const user = await requireUser()
  return NextResponse.json({ data: await listFolders(user.id) })
})

export const POST = withErrorHandling(async (request: Request) => {
  const user = await requireUser()
  const input = await parseBody(request, createFolderSchema)

  return NextResponse.json({ data: await createFolder(user.id, input) }, { status: 201 })
})
