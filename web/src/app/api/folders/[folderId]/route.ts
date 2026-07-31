import { NextResponse } from 'next/server'

import { updateFolderSchema } from '@/lib/validations/chat'
import { parseBody, requireUser, withErrorHandling } from '@/server/http'
import { deleteFolder, updateFolder } from '@/server/services/folder-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type RouteContext = { params: Promise<{ folderId: string }> }

export const PATCH = withErrorHandling(
  async (request: Request, context: RouteContext) => {
    const user = await requireUser()
    const { folderId } = await context.params
    const input = await parseBody(request, updateFolderSchema)

    return NextResponse.json({ data: await updateFolder(user.id, folderId, input) })
  },
)

export const DELETE = withErrorHandling(
  async (_request: Request, context: RouteContext) => {
    const user = await requireUser()
    const { folderId } = await context.params
    await deleteFolder(user.id, folderId)

    return new NextResponse(null, { status: 204 })
  },
)
