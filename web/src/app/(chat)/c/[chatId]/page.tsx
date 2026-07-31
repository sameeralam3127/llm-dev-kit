import type { Metadata } from 'next'
import { notFound, redirect } from 'next/navigation'

import { ChatView } from '@/components/chat/chat-view'
import { ErrorBoundary } from '@/components/error-boundary'
import { auth } from '@/lib/auth'
import { ROUTES } from '@/lib/constants'
import { ApiError } from '@/server/http'
import { getChat } from '@/server/services/chat-service'

export const dynamic = 'force-dynamic'

interface PageProps {
  params: Promise<{ chatId: string }>
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const session = await auth()
  if (!session?.user?.id) return { title: 'Chat' }

  const { chatId } = await params
  try {
    const chat = await getChat(session.user.id, chatId)
    return { title: chat.title }
  } catch {
    return { title: 'Chat' }
  }
}

export default async function ChatPage({ params }: PageProps) {
  const session = await auth()
  if (!session?.user?.id) redirect(ROUTES.login)

  const { chatId } = await params

  // Fetched on the server so the transcript is in the first paint rather than
  // arriving after a client round-trip.
  let chat
  try {
    chat = await getChat(session.user.id, chatId)
  } catch (error) {
    if (error instanceof ApiError && error.code === 'not_found') notFound()
    throw error
  }

  return (
    <ErrorBoundary>
      <ChatView
        chat={chat}
        user={{
          name: session.user.name ?? null,
          email: session.user.email ?? null,
          image: session.user.image ?? null,
        }}
      />
    </ErrorBoundary>
  )
}
