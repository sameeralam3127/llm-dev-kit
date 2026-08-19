import type {
  ChatDetail,
  ChatSummary,
  Folder,
  ModelInfo,
} from '@/types/chat'
import type {
  CreateChatInput,
  CreateFolderInput,
  UpdateChatInput,
  UpdateFolderInput,
} from '@/lib/validations/chat'

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string

  constructor(message: string, status: number, code: string) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
  }
}

interface ApiEnvelope<T> {
  data: T
  meta?: Record<string, unknown>
}

interface ApiErrorEnvelope {
  error?: { message?: string; code?: string }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })

  if (response.status === 204) return undefined as T

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    let code = 'internal'
    try {
      const payload = (await response.json()) as ApiErrorEnvelope
      if (payload.error?.message) message = payload.error.message
      if (payload.error?.code) code = payload.error.code
    } catch {
      /* non-JSON error body — the status-based message stands */
    }
    throw new ApiClientError(message, response.status, code)
  }

  const payload = (await response.json()) as ApiEnvelope<T>
  return payload.data
}

export interface ListChatsParams {
  q?: string
  folderId?: string
  archived?: boolean
}

export const api = {
  chats: {
    list(params: ListChatsParams = {}, signal?: AbortSignal): Promise<ChatSummary[]> {
      const search = new URLSearchParams()
      if (params.q) search.set('q', params.q)
      if (params.folderId) search.set('folderId', params.folderId)
      if (params.archived) search.set('archived', 'true')

      const query = search.toString()
      return request(`/api/chats${query ? `?${query}` : ''}`, { signal })
    },

    get(chatId: string, signal?: AbortSignal): Promise<ChatDetail> {
      return request(`/api/chats/${chatId}`, { signal })
    },

    create(input: CreateChatInput = {}): Promise<ChatSummary> {
      return request('/api/chats', {
        method: 'POST',
        body: JSON.stringify(input),
      })
    },

    update(chatId: string, input: UpdateChatInput): Promise<ChatSummary> {
      return request(`/api/chats/${chatId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      })
    },

    remove(chatId: string): Promise<void> {
      return request(`/api/chats/${chatId}`, { method: 'DELETE' })
    },

    removeMessage(chatId: string, messageId: string): Promise<void> {
      return request(`/api/chats/${chatId}/messages/${messageId}`, {
        method: 'DELETE',
      })
    },
  },

  folders: {
    list(signal?: AbortSignal): Promise<Folder[]> {
      return request('/api/folders', { signal })
    },

    create(input: CreateFolderInput): Promise<Folder> {
      return request('/api/folders', {
        method: 'POST',
        body: JSON.stringify(input),
      })
    },

    update(folderId: string, input: UpdateFolderInput): Promise<Folder> {
      return request(`/api/folders/${folderId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      })
    },

    remove(folderId: string): Promise<void> {
      return request(`/api/folders/${folderId}`, { method: 'DELETE' })
    },
  },

  models: {
    list(signal?: AbortSignal): Promise<ModelInfo[]> {
      return request('/api/models', { signal })
    },
  },

  auth: {
    async register(input: {
      name: string
      email: string
      password: string
    }): Promise<{ id: string; email: string }> {
      return request('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(input),
      })
    },
  },
}

/** Shared query keys so mutations can invalidate precisely. */
export const queryKeys = {
  chats: (params: ListChatsParams = {}) => ['chats', params] as const,
  chat: (chatId: string) => ['chat', chatId] as const,
  folders: () => ['folders'] as const,
  models: () => ['models'] as const,
}
