import 'server-only'

import type {
  Chat as ChatRow,
  Folder as FolderRow,
  Message as MessageRow,
  MessageVersion as MessageVersionRow,
} from '@prisma/client'

import { FOLDER_COLORS, type FolderColorId } from '@/lib/constants'
import type {
  ChatMessage,
  ChatSummary,
  Folder,
  MessageRole,
  MessageVersion,
} from '@/types/chat'

const VALID_ROLES = new Set<MessageRole>(['user', 'assistant', 'system'])
const VALID_COLORS = new Set<string>(FOLDER_COLORS.map((color) => color.id))

/**
 * The schema stores role and color as plain strings so it stays portable across
 * databases; these narrow them back to the union types at the boundary.
 */
function toRole(value: string): MessageRole {
  return VALID_ROLES.has(value as MessageRole) ? (value as MessageRole) : 'assistant'
}

function toColor(value: string): FolderColorId {
  return VALID_COLORS.has(value) ? (value as FolderColorId) : 'slate'
}

export function toMessageVersionDTO(row: MessageVersionRow): MessageVersion {
  return {
    id: row.id,
    content: row.content,
    model: row.model,
    position: row.position,
    createdAt: row.createdAt.toISOString(),
  }
}

export function toMessageDTO(
  row: MessageRow & { versions?: MessageVersionRow[] },
): ChatMessage {
  return {
    id: row.id,
    chatId: row.chatId,
    role: toRole(row.role),
    content: row.content,
    position: row.position,
    model: row.model,
    error: row.error,
    truncated: row.truncated,
    editedAt: row.editedAt?.toISOString() ?? null,
    createdAt: row.createdAt.toISOString(),
    versions: (row.versions ?? []).map(toMessageVersionDTO),
  }
}

export function toChatSummaryDTO(
  row: ChatRow & { _count?: { messages: number } },
): ChatSummary {
  return {
    id: row.id,
    title: row.title,
    model: row.model,
    pinned: row.pinned,
    archived: row.archived,
    folderId: row.folderId,
    shareId: row.shareId,
    updatedAt: row.updatedAt.toISOString(),
    createdAt: row.createdAt.toISOString(),
    messageCount: row._count?.messages ?? 0,
  }
}

export function toFolderDTO(
  row: FolderRow & { _count?: { chats: number } },
): Folder {
  return {
    id: row.id,
    name: row.name,
    color: toColor(row.color),
    position: row.position,
    createdAt: row.createdAt.toISOString(),
    chatCount: row._count?.chats ?? 0,
  }
}
