import type { Role } from '@/lib/roles'

export interface AdminUser {
  id: string
  name: string | null
  email: string
  role: Role
  /** How they can sign in: "password", "github", "keycloak". */
  signIn: string[]
  createdAt: string
  chatCount: number
  apiKeyCount: number
}

export type CheckStatus = 'ok' | 'degraded' | 'down' | 'off'

export interface HealthCheck {
  name: string
  status: CheckStatus
  /** One line for the person reading the page. */
  detail: string
}

export interface AdminHealth {
  checkedAt: string
  checks: HealthCheck[]
  counts: { users: number; chats: number; apiKeys: number; indexedChunks: number | null }
}

/** One day of activity, oldest first. `date` is `yyyy-MM-dd` in UTC. */
export interface ActivityDay {
  date: string
  messages: number
  chats: number
}

export interface AdminOverview {
  counts: {
    users: number
    admins: number
    chats: number
    messages: number
    sharedChats: number
    apiKeys: number
  }
  /** The last 14 days, today included. */
  activity: ActivityDay[]
  recentUsers: Pick<AdminUser, 'id' | 'name' | 'email' | 'role' | 'createdAt'>[]
}

/** Any user's API key, as an admin sees it. The key itself is never listed. */
export interface AdminApiKey {
  id: string
  name: string
  prefix: string
  owner: { id: string; name: string | null; email: string }
  createdAt: string
  lastUsedAt: string | null
  revokedAt: string | null
}

export type StoreStatus = 'connected' | 'offline' | 'unreachable'

export interface DocumentStats {
  index: { status: StoreStatus; chunks: number | null }
  cache: { status: StoreStatus; answers: number | null }
}

export interface UploadResult {
  filename: string
  chunks: number
  /** Cached answers dropped, so no answer predates the new document. */
  cacheCleared: number | null
}

/** Read-only instance settings. Values come from `.env`; secrets are never included. */
export interface AdminConfig {
  publicUrl: string | null
  registrationOpen: boolean
  signIn: { password: boolean; github: boolean; sso: boolean }
  defaultModel: string
  identity: { issuer: string; audience: string }
  services: { rag: string; llm: string }
}
