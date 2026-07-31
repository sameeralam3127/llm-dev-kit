import { NextResponse } from 'next/server'

import { updateChatSchema } from '@/lib/validations/chat'
import { parseBody, requireUser, withErrorHandling } from '@/server/http'
import { deleteChat, getChat, updateChat } from '@/server/services/chat-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/** Next 15 hands route params to handlers as a promise. */
type RouteContext = { params: Promise<{ chatId: string }> }

export const GET = withErrorHandling(
  async (_request: Request, context: RouteContext) => {
    const user = await requireUser()
    const { chatId } = await context.params

    return NextResponse.json({ data: await getChat(user.id, chatId) })
  },
)

export const PATCH = withErrorHandling(
  async (request: Request, context: RouteContext) => {
    const user = await requireUser()
    const { chatId } = await context.params
    const input = await parseBody(request, updateChatSchema)

    return NextResponse.json({ data: await updateChat(user.id, chatId, input) })
  },
)

export const DELETE = withErrorHandling(
  async (_request: Request, context: RouteContext) => {
    const user = await requireUser()
    const { chatId } = await context.params
    await deleteChat(user.id, chatId)

    return new NextResponse(null, { status: 204 })
  },
)
