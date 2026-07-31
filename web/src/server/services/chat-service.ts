import 'server-only'

import { nanoid } from 'nanoid'

import { LIMITS } from '@/lib/constants'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import type { ProviderMessage } from '@/lib/llm/types'
import { deriveTitle } from '@/lib/utils'
import type {
  CreateChatInput,
  SendMessageInput,
  UpdateChatInput,
} from '@/lib/validations/chat'
import { ApiError, badRequest, notFound } from '@/server/http'
import { toChatSummaryDTO, toMessageDTO } from '@/server/mappers'
import type { ChatDetail, ChatMessage, ChatSummary } from '@/types/chat'

const messageInclude = {
  versions: { orderBy: { position: 'asc' } },
} as const

interface ListChatsOptions {
  q?: string | undefined
  folderId?: string | undefined
  archived?: boolean | undefined
}

export async function listChats(
  userId: string,
  options: ListChatsOptions = {},
): Promise<ChatSummary[]> {
  const { q, folderId, archived = false } = options

  const rows = await db.chat.findMany({
    where: {
      userId,
      archived,
      ...(folderId === undefined
        ? {}
        : { folderId: folderId === 'none' ? null : folderId }),
      ...(q
        ? {
            OR: [
              { title: { contains: q } },
              { messages: { some: { content: { contains: q } } } },
            ],
          }
        : {}),
    },
    orderBy: [{ pinned: 'desc' }, { updatedAt: 'desc' }],
    include: { _count: { select: { messages: true } } },
    take: 300,
  })

  return rows.map(toChatSummaryDTO)
}

export async function getChat(
  userId: string,
  chatId: string,
): Promise<ChatDetail> {
  const chat = await db.chat.findFirst({
    where: { id: chatId, userId },
    include: {
      _count: { select: { messages: true } },
      messages: { orderBy: { position: 'asc' }, include: messageInclude },
    },
  })

  if (!chat) throw notFound('Chat')

  return {
    ...toChatSummaryDTO(chat),
    systemPrompt: chat.systemPrompt,
    messages: chat.messages.map(toMessageDTO),
  }
}

/** Public, read-only view used by /share/[shareId]. Never exposes the owner. */
export async function getSharedChat(shareId: string): Promise<{
  title: string
  model: string
  sharedAt: string | null
  messages: ChatMessage[]
} | null> {
  const chat = await db.chat.findUnique({
    where: { shareId },
    include: {
      messages: {
        orderBy: { position: 'asc' },
        where: { role: { not: 'system' } },
        include: messageInclude,
      },
    },
  })

  if (!chat) return null

  return {
    title: chat.title,
    model: chat.model,
    sharedAt: chat.sharedAt?.toISOString() ?? null,
    messages: chat.messages.map(toMessageDTO),
  }
}

export async function createChat(
  userId: string,
  input: CreateChatInput,
): Promise<ChatSummary> {
  if (input.folderId) {
    await assertFolderOwned(userId, input.folderId)
  }

  const chat = await db.chat.create({
    data: {
      userId,
      title: input.title ?? 'New chat',
      model: input.model ?? getEnv().DEFAULT_MODEL,
      folderId: input.folderId ?? null,
      systemPrompt: input.systemPrompt ?? null,
    },
    include: { _count: { select: { messages: true } } },
  })

  return toChatSummaryDTO(chat)
}

export async function updateChat(
  userId: string,
  chatId: string,
  input: UpdateChatInput,
): Promise<ChatSummary> {
  const existing = await db.chat.findFirst({
    where: { id: chatId, userId },
    select: { id: true, shareId: true },
  })
  if (!existing) throw notFound('Chat')

  if (input.folderId) {
    await assertFolderOwned(userId, input.folderId)
  }

  // Toggling `shared` mints or revokes the public slug. Revoking and re-sharing
  // deliberately produces a new slug so old links stop resolving.
  const shareFields =
    input.shared === undefined
      ? {}
      : input.shared
        ? {
            shareId: existing.shareId ?? nanoid(16),
            sharedAt: existing.shareId ? undefined : new Date(),
          }
        : { shareId: null, sharedAt: null }

  const chat = await db.chat.update({
    where: { id: chatId },
    data: {
      ...(input.title === undefined ? {} : { title: input.title }),
      ...(input.model === undefined ? {} : { model: input.model }),
      ...(input.folderId === undefined ? {} : { folderId: input.folderId }),
      ...(input.systemPrompt === undefined
        ? {}
        : { systemPrompt: input.systemPrompt }),
      ...(input.pinned === undefined ? {} : { pinned: input.pinned }),
      ...(input.archived === undefined ? {} : { archived: input.archived }),
      ...shareFields,
    },
    include: { _count: { select: { messages: true } } },
  })

  return toChatSummaryDTO(chat)
}

export async function deleteChat(userId: string, chatId: string): Promise<void> {
  const result = await db.chat.deleteMany({ where: { id: chatId, userId } })
  if (result.count === 0) throw notFound('Chat')
}

export async function deleteMessage(
  userId: string,
  chatId: string,
  messageId: string,
): Promise<void> {
  const message = await db.message.findFirst({
    where: { id: messageId, chatId, chat: { userId } },
    select: { id: true },
  })
  if (!message) throw notFound('Message')

  await db.message.delete({ where: { id: messageId } })
  await touchChat(chatId)
}

// ---------------------------------------------------------------------------
// Turn preparation
// ---------------------------------------------------------------------------

export interface PreparedTurn {
  chatId: string
  title: string
  userMessage: ChatMessage
  assistantMessageId: string
  model: string
  providerMessages: ProviderMessage[]
}

/**
 * Applies the write half of a turn — appending, editing, or rewinding history —
 * and returns the prompt to stream against.
 *
 * All three intents converge on the same end state: a user message that is last
 * in the conversation, followed by exactly one empty assistant row waiting to be
 * filled by the stream. Anything after the edit/regenerate point is discarded,
 * because a reply the user rewound past can no longer be consistent with what
 * follows it.
 */
export async function prepareTurn(
  userId: string,
  input: SendMessageInput,
): Promise<PreparedTurn> {
  const chat = await db.chat.findFirst({
    where: { id: input.chatId, userId },
    include: { messages: { orderBy: { position: 'asc' } } },
  })
  if (!chat) throw notFound('Chat')

  const model = input.model ?? chat.model
  const messages = chat.messages

  return db.$transaction(async (tx) => {
    let userMessageRow
    let assistantMessageId: string
    let historyEnd: number

    if (input.intent === 'send') {
      const content = input.content
      if (!content) throw badRequest('content is required')

      const nextPosition = (messages.at(-1)?.position ?? -1) + 1

      userMessageRow = await tx.message.create({
        data: {
          chatId: chat.id,
          role: 'user',
          content,
          position: nextPosition,
        },
        include: messageInclude,
      })

      const assistant = await tx.message.create({
        data: {
          chatId: chat.id,
          role: 'assistant',
          content: '',
          position: nextPosition + 1,
          model,
        },
      })
      assistantMessageId = assistant.id
      historyEnd = nextPosition
    } else if (input.intent === 'edit') {
      const target = messages.find((m) => m.id === input.targetMessageId)
      if (!target) throw notFound('Message')
      if (target.role !== 'user') {
        throw badRequest('Only your own messages can be edited')
      }

      const content = input.content
      if (!content) throw badRequest('content is required')

      // Keep the pre-edit text so the UI can show that the turn was revised.
      await tx.messageVersion.create({
        data: {
          messageId: target.id,
          content: target.content,
          model: target.model,
          position: await nextVersionPosition(tx, target.id),
        },
      })

      userMessageRow = await tx.message.update({
        where: { id: target.id },
        data: { content, editedAt: new Date(), error: null, truncated: false },
        include: messageInclude,
      })

      await tx.message.deleteMany({
        where: { chatId: chat.id, position: { gt: target.position } },
      })

      const assistant = await tx.message.create({
        data: {
          chatId: chat.id,
          role: 'assistant',
          content: '',
          position: target.position + 1,
          model,
        },
      })
      assistantMessageId = assistant.id
      historyEnd = target.position
    } else {
      // regenerate — reuse the assistant row so its id (and any deep link to it)
      // survives, archiving the answer being replaced.
      const target =
        messages.find((m) => m.id === input.targetMessageId) ??
        [...messages].reverse().find((m) => m.role === 'assistant')

      if (!target) throw notFound('Message')
      if (target.role !== 'assistant') {
        throw badRequest('Only assistant replies can be regenerated')
      }

      const precedingUser = [...messages]
        .filter((m) => m.position < target.position && m.role === 'user')
        .at(-1)
      if (!precedingUser) {
        throw badRequest('Nothing to regenerate from')
      }

      if (target.content.trim()) {
        await tx.messageVersion.create({
          data: {
            messageId: target.id,
            content: target.content,
            model: target.model,
            position: await nextVersionPosition(tx, target.id),
          },
        })
      }

      await tx.message.deleteMany({
        where: { chatId: chat.id, position: { gt: target.position } },
      })

      await tx.message.update({
        where: { id: target.id },
        data: { content: '', error: null, truncated: false, model },
      })

      userMessageRow = await tx.message.findUniqueOrThrow({
        where: { id: precedingUser.id },
        include: messageInclude,
      })
      assistantMessageId = target.id
      historyEnd = target.position - 1
    }

    const history = await tx.message.findMany({
      where: {
        chatId: chat.id,
        position: { lte: historyEnd },
        role: { not: 'system' },
      },
      orderBy: { position: 'asc' },
      select: { role: true, content: true },
    })

    const title =
      chat.title === 'New chat' && userMessageRow.role === 'user'
        ? deriveTitle(userMessageRow.content)
        : chat.title

    await tx.chat.update({
      where: { id: chat.id },
      data: { title, model, updatedAt: new Date() },
    })

    return {
      chatId: chat.id,
      title,
      userMessage: toMessageDTO(userMessageRow),
      assistantMessageId,
      model,
      providerMessages: buildProviderMessages(chat.systemPrompt, history),
    }
  })
}

function buildProviderMessages(
  systemPrompt: string | null,
  history: Array<{ role: string; content: string }>,
): ProviderMessage[] {
  const trimmed = history
    .filter((message) => message.content.trim().length > 0)
    .slice(-LIMITS.contextWindowMessages)
    .map((message) => ({
      role: message.role === 'user' ? ('user' as const) : ('assistant' as const),
      content: message.content,
    }))

  return systemPrompt?.trim()
    ? [{ role: 'system', content: systemPrompt.trim() }, ...trimmed]
    : trimmed
}

/**
 * Commits whatever the stream produced. Called on success, on user-cancel, and
 * on upstream failure, so a partial answer is never silently lost.
 */
export async function finalizeAssistantMessage(params: {
  messageId: string
  chatId: string
  content: string
  model: string
  truncated: boolean
  error?: string | null
}): Promise<void> {
  await db.message.update({
    where: { id: params.messageId },
    data: {
      content: params.content,
      model: params.model,
      truncated: params.truncated,
      error: params.error ?? null,
    },
  })
  await touchChat(params.chatId)
}

async function touchChat(chatId: string): Promise<void> {
  await db.chat.update({
    where: { id: chatId },
    data: { updatedAt: new Date() },
  })
}

async function nextVersionPosition(
  tx: Pick<typeof db, 'messageVersion'>,
  messageId: string,
): Promise<number> {
  const last = await tx.messageVersion.findFirst({
    where: { messageId },
    orderBy: { position: 'desc' },
    select: { position: true },
  })
  return (last?.position ?? -1) + 1
}

async function assertFolderOwned(userId: string, folderId: string): Promise<void> {
  const folder = await db.folder.findFirst({
    where: { id: folderId, userId },
    select: { id: true },
  })
  if (!folder) {
    throw new ApiError('not_found', 'Folder not found')
  }
}
