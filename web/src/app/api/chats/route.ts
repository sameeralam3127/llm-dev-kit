import { NextResponse } from 'next/server'

import { createChatSchema, listChatsQuerySchema } from '@/lib/validations/chat'
import { parseBody, parseQuery, requireUser, withErrorHandling } from '@/server/http'
import { createChat, listChats } from '@/server/services/chat-service'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export const GET = withErrorHandling(async (request: Request) => {
  const user = await requireUser()
  const query = parseQuery(request, listChatsQuerySchema)

  const chats = await listChats(user.id, {
    q: query.q,
    folderId: query.folderId,
    archived: query.archived,
  })

  return NextResponse.json({ data: chats })
})

export const POST = withErrorHandling(async (request: Request) => {
  const user = await requireUser()
  const input = await parseBody(request, createChatSchema)
  const chat = await createChat(user.id, input)

  return NextResponse.json({ data: chat }, { status: 201 })
})
