import { NextResponse } from 'next/server'

import { requireUser, withErrorHandling } from '@/server/http'
import { deleteMessage } from '@/server/services/chat-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type RouteContext = { params: Promise<{ chatId: string; messageId: string }> }

/**
 * Editing a message goes through POST /api/chat with intent "edit", because it
 * rewinds history and immediately regenerates. This endpoint only removes a
 * single message — used to clear a failed reply.
 */
export const DELETE = withErrorHandling(
  async (_request: Request, context: RouteContext) => {
    const user = await requireUser()
    const { chatId, messageId } = await context.params
    await deleteMessage(user.id, chatId, messageId)

    return new NextResponse(null, { status: 204 })
  },
)
