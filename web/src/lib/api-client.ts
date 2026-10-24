import type {
  ChatDetail,
  ChatSummary,
  Folder,
  ModelInfo,
} from '@/types/chat'
import type { Role } from '@/lib/roles'
import type {
  AdminApiKey,
  AdminHealth,
  AdminOverview,
  AdminUser,
  DocumentStats,
  UploadResult,
} from '@/types/admin'
import type { ApiKeySummary, CreatedApiKey } from '@/types/api-key'
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
      // FormData sets its own multipart boundary; only JSON strings are labelled.
      ...(typeof init.body === 'string' ? { 'Content-Type': 'application/json' } : {}),
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

  admin: {
    users(signal?: AbortSignal): Promise<AdminUser[]> {
      return request('/api/admin/users', { signal })
    },

    setRole(userId: string, role: Role): Promise<AdminUser> {
      return request(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      })
    },

    health(signal?: AbortSignal): Promise<AdminHealth> {
      return request('/api/admin/health', { signal })
    },

    overview(signal?: AbortSignal): Promise<AdminOverview> {
      return request('/api/admin/overview', { signal })
    },

    apiKeys(signal?: AbortSignal): Promise<AdminApiKey[]> {
      return request('/api/admin/api-keys', { signal })
    },

    revokeApiKey(keyId: string): Promise<void> {
      return request(`/api/admin/api-keys/${keyId}`, { method: 'DELETE' })
    },

    documents(signal?: AbortSignal): Promise<DocumentStats> {
      return request('/api/admin/documents', { signal })
    },

    uploadDocument(file: File): Promise<UploadResult> {
      const body = new FormData()
      body.append('file', file)
      return request('/api/admin/documents', { method: 'POST', body })
    },

    clearDocuments(): Promise<{ cacheCleared: number | null }> {
      return request('/api/admin/documents/clear', { method: 'POST' })
    },

    clearCache(): Promise<{ cleared: number }> {
      return request('/api/admin/cache/clear', { method: 'POST' })
    },
  },

  keys: {
    list(signal?: AbortSignal): Promise<ApiKeySummary[]> {
      return request('/api/keys', { signal })
    },

    create(name: string): Promise<CreatedApiKey> {
      return request('/api/keys', { method: 'POST', body: JSON.stringify({ name }) })
    },

    revoke(keyId: string): Promise<void> {
      return request(`/api/keys/${keyId}`, { method: 'DELETE' })
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
  apiKeys: () => ['api-keys'] as const,
  adminUsers: () => ['admin', 'users'] as const,
  adminHealth: () => ['admin', 'health'] as const,
  adminOverview: () => ['admin', 'overview'] as const,
  adminApiKeys: () => ['admin', 'api-keys'] as const,
  adminDocuments: () => ['admin', 'documents'] as const,
}
