import type { FolderColorId } from '@/lib/constants'

export type MessageRole = 'user' | 'assistant' | 'system'

/** Client-facing message. Dates are ISO strings — these cross the wire as JSON. */
export interface ChatMessage {
  id: string
  chatId: string
  role: MessageRole
  content: string
  position: number
  model: string | null
  error: string | null
  truncated: boolean
  editedAt: string | null
  createdAt: string
  /** Archived previous answers, oldest first. Assistant messages only. */
  versions: MessageVersion[]
}

export interface MessageVersion {
  id: string
  content: string
  model: string | null
  position: number
  createdAt: string
}

/** Chat without its messages — what the sidebar lists. */
export interface ChatSummary {
  id: string
  title: string
  model: string
  pinned: boolean
  archived: boolean
  folderId: string | null
  shareId: string | null
  updatedAt: string
  createdAt: string
  messageCount: number
}

export interface ChatDetail extends ChatSummary {
  systemPrompt: string | null
  messages: ChatMessage[]
}

export interface Folder {
  id: string
  name: string
  color: FolderColorId
  position: number
  createdAt: string
  chatCount: number
}

export interface ModelInfo {
  id: string
  label: string
  provider: string
}

/**
 * Server → client streaming protocol. Newline-delimited JSON over a single
 * `text/event-stream`-flavoured response; every frame is one of these.
 */
export type StreamEvent =
  | {
      type: 'meta'
      chatId: string
      title: string
      userMessageId: string
      assistantMessageId: string
    }
  | { type: 'delta'; text: string }
  | { type: 'done'; content: string; truncated: boolean }
  | { type: 'error'; message: string; code: StreamErrorCode }

export type StreamErrorCode =
  | 'unauthorized'
  | 'not_found'
  | 'rate_limited'
  | 'upstream_unavailable'
  | 'upstream_error'
  | 'timeout'
  | 'invalid_request'
  | 'internal'

/** Body accepted by POST /api/chat. */
export interface SendMessagePayload {
  chatId: string
  /** Omitted when regenerating or re-running after an edit. */
  content?: string
  /**
   * - `send`: append a new user message
   * - `regenerate`: replace the trailing assistant answer
   * - `edit`: rewrite `targetMessageId` and drop everything after it
   */
  intent: 'send' | 'regenerate' | 'edit'
  targetMessageId?: string
  model?: string
}
