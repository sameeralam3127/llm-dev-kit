import 'server-only'

import { oauthProvidersEnabled } from '@/lib/auth'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import { asRole, type Role } from '@/lib/roles'
import { ApiError, type ApiErrorCode, notFound } from '@/server/http'
import { mintAccessToken } from '@/server/identity/tokens'
import type {
  ActivityDay,
  AdminApiKey,
  AdminConfig,
  AdminHealth,
  AdminOverview,
  AdminUser,
  DocumentStats,
  HealthCheck,
  StoreStatus,
  UploadResult,
} from '@/types/admin'

const CHECK_TIMEOUT_MS = 3_000
/** Indexing embeds every chunk, one at a time on a CPU-only host; allow for it. */
const UPLOAD_TIMEOUT_MS = 15 * 60_000
const ACTIVITY_DAYS = 14
const DAY_MS = 86_400_000

export async function listUsers(): Promise<AdminUser[]> {
  const rows = await db.user.findMany({
    orderBy: [{ createdAt: 'asc' }, { id: 'asc' }],
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      passwordHash: true,
      createdAt: true,
      accounts: { select: { provider: true } },
      _count: { select: { chats: true, apiKeys: { where: { revokedAt: null } } } },
    },
  })
  return rows.map((row) => ({
    id: row.id,
    name: row.name,
    email: row.email,
    role: asRole(row.role),
    signIn: [...(row.passwordHash ? ['password'] : []), ...row.accounts.map((a) => a.provider)],
    createdAt: row.createdAt.toISOString(),
    chatCount: row._count.chats,
    apiKeyCount: row._count.apiKeys,
  }))
}

/**
 * Change a user's role. The instance always keeps at least one admin, so the
 * last one cannot be demoted, not even by themselves. Tokens already issued
 * keep their old role for at most five minutes; API keys follow at once.
 */
export async function setUserRole(userId: string, role: Role): Promise<AdminUser> {
  await db.$transaction(async (tx) => {
    const target = await tx.user.findUnique({ where: { id: userId }, select: { role: true } })
    if (!target) throw notFound('User')

    if (asRole(target.role) === 'admin' && role !== 'admin') {
      const admins = await tx.user.count({ where: { role: 'admin' } })
      if (admins <= 1) {
        throw new ApiError('conflict', 'There must be at least one admin; promote someone else first')
      }
    }
    await tx.user.update({ where: { id: userId }, data: { role } })
  })

  const updated = (await listUsers()).find((user) => user.id === userId)
  if (!updated) throw notFound('User')
  return updated
}

async function probe(url: string, init: RequestInit = {}): Promise<Response | null> {
  try {
    return await fetch(url, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(CHECK_TIMEOUT_MS),
    })
  } catch {
    return null
  }
}

/** What the admin page shows: each service's state and a few totals. */
export async function getHealth(adminId: string): Promise<AdminHealth> {
  const env = getEnv()
  const { token } = await mintAccessToken(adminId)
  const asAdmin = { headers: { Authorization: `Bearer ${token}` } }

  const [rag, llm, docs, cache, keycloak, counts, newestKey] = await Promise.all([
    probe(`${env.RAG_SERVICE_URL}/health`),
    probe(`${env.LLM_SERVICE_URL}/health`),
    probe(`${env.RAG_SERVICE_URL}/documents/stats`, asAdmin),
    probe(`${env.RAG_SERVICE_URL}/cache/stats`, asAdmin),
    env.AUTH_KEYCLOAK_ISSUER
      ? probe(
          `${(env.AUTH_KEYCLOAK_INTERNAL_ISSUER || env.AUTH_KEYCLOAK_ISSUER).replace(/\/$/, '')}/.well-known/openid-configuration`,
        )
      : Promise.resolve(undefined),
    Promise.all([
      db.user.count(),
      db.chat.count(),
      db.apiKey.count({ where: { revokedAt: null } }),
    ]),
    db.signingKey.findFirst({ orderBy: { createdAt: 'desc' }, select: { createdAt: true } }),
  ])

  const [llmBody, docsBody, cacheBody] = await Promise.all([json(llm), json(docs), json(cache)])
  const [users, chats, apiKeys] = counts

  const checks: HealthCheck[] = [
    { name: 'Web app', status: 'ok', detail: 'Serving this page; database reachable' },
    reachable('RAG service', rag, 'Answering'),
    !llm
      ? { name: 'Model service', status: 'down', detail: 'Unreachable' }
      : llmBody?.['offline_ready'] === true
        ? { name: 'Model service', status: 'ok', detail: 'Ollama reachable; local models ready' }
        : {
            name: 'Model service',
            status: llm.ok ? 'degraded' : 'down',
            detail: 'Ollama unreachable or the embedding model is missing',
          },
    !docsBody
      ? { name: 'Document index', status: 'down', detail: unreadable(docs) }
      : docsBody['status'] === 'connected'
        ? { name: 'Document index', status: 'ok', detail: `${String(docsBody['document_count'])} chunks indexed` }
        : { name: 'Document index', status: 'down', detail: 'Vector store unreachable' },
    !cacheBody
      ? { name: 'Answer cache', status: 'down', detail: unreadable(cache) }
      : cacheBody['status'] === 'connected'
        ? { name: 'Answer cache', status: 'ok', detail: `${String(cacheBody['keys'] ?? 0)} cached answers` }
        : { name: 'Answer cache', status: 'degraded', detail: 'Redis unreachable; answers are not cached' },
    keycloak === undefined
      ? { name: 'Single sign-on', status: 'off', detail: 'Not configured' }
      : reachable('Single sign-on', keycloak, 'Keycloak answering'),
    signingKeyCheck(newestKey?.createdAt ?? null),
  ]

  return {
    checkedAt: new Date().toISOString(),
    checks,
    counts: {
      users,
      chats,
      apiKeys,
      indexedChunks:
        typeof docsBody?.['document_count'] === 'number' ? docsBody['document_count'] : null,
    },
  }
}

async function json(res: Response | null): Promise<Record<string, unknown> | null> {
  if (!res?.ok) return null
  return (await res.json().catch(() => null)) as Record<string, unknown> | null
}

function unreadable(res: Response | null): string {
  return res ? `Responded ${res.status}` : 'RAG service unreachable'
}

function reachable(name: string, res: Response | null, detail: string): HealthCheck {
  if (!res) return { name, status: 'down', detail: 'Unreachable' }
  if (!res.ok) return { name, status: 'down', detail: `Responded ${res.status}` }
  return { name, status: 'ok', detail }
}

const ROTATION_WARNING_DAYS = 35

function signingKeyCheck(createdAt: Date | null): HealthCheck {
  const name = 'Signing key'
  if (!createdAt) return { name, status: 'degraded', detail: 'None yet; one is made on first use' }
  const days = Math.floor((Date.now() - createdAt.getTime()) / 86_400_000)
  return days > ROTATION_WARNING_DAYS
    ? { name, status: 'degraded', detail: `${days} days old; rotation is overdue` }
    : { name, status: 'ok', detail: `${days} day${days === 1 ? '' : 's'} old; rotates every 30` }
}

// ---------------------------------------------------------------- overview

/** Totals, the last two weeks of activity and the newest accounts. */
export async function getOverview(): Promise<AdminOverview> {
  const today = new Date()
  today.setUTCHours(0, 0, 0, 0)
  const since = new Date(today.getTime() - (ACTIVITY_DAYS - 1) * DAY_MS)

  const [users, admins, chats, messages, sharedChats, apiKeys, recent, questions, newChats] =
    await Promise.all([
      db.user.count(),
      db.user.count({ where: { role: 'admin' } }),
      db.chat.count(),
      db.message.count(),
      db.chat.count({ where: { shareId: { not: null } } }),
      db.apiKey.count({ where: { revokedAt: null } }),
      db.user.findMany({
        orderBy: [{ createdAt: 'desc' }, { id: 'asc' }],
        take: 5,
        select: { id: true, name: true, email: true, role: true, createdAt: true },
      }),
      // Two weeks of timestamps, bucketed below: one query each instead of a
      // count per day, and no SQL dialect-specific date functions.
      db.message.findMany({
        where: { role: 'user', createdAt: { gte: since } },
        select: { createdAt: true },
      }),
      db.chat.findMany({ where: { createdAt: { gte: since } }, select: { createdAt: true } }),
    ])

  const activity: ActivityDay[] = Array.from({ length: ACTIVITY_DAYS }, (_, i) => ({
    date: new Date(since.getTime() + i * DAY_MS).toISOString().slice(0, 10),
    messages: 0,
    chats: 0,
  }))
  const dayOf = (at: Date) => Math.floor((at.getTime() - since.getTime()) / DAY_MS)
  for (const { createdAt } of questions) {
    const day = activity[dayOf(createdAt)]
    if (day) day.messages += 1
  }
  for (const { createdAt } of newChats) {
    const day = activity[dayOf(createdAt)]
    if (day) day.chats += 1
  }

  return {
    counts: { users, admins, chats, messages, sharedChats, apiKeys },
    activity,
    recentUsers: recent.map((user) => ({
      ...user,
      role: asRole(user.role),
      createdAt: user.createdAt.toISOString(),
    })),
  }
}

// ---------------------------------------------------------------- API keys

/** Every user's keys, newest first. */
export async function listAllApiKeys(): Promise<AdminApiKey[]> {
  const rows = await db.apiKey.findMany({
    orderBy: [{ createdAt: 'desc' }, { id: 'asc' }],
    select: {
      id: true,
      name: true,
      prefix: true,
      createdAt: true,
      lastUsedAt: true,
      revokedAt: true,
      user: { select: { id: true, name: true, email: true } },
    },
  })
  return rows.map((row) => ({
    id: row.id,
    name: row.name,
    prefix: row.prefix,
    owner: row.user,
    createdAt: row.createdAt.toISOString(),
    lastUsedAt: row.lastUsedAt?.toISOString() ?? null,
    revokedAt: row.revokedAt?.toISOString() ?? null,
  }))
}

/**
 * Revoke anyone's key. The Python services cache a verified key for at most
 * a minute, so it stops working within one.
 */
export async function revokeAnyApiKey(keyId: string): Promise<void> {
  const result = await db.apiKey.updateMany({
    where: { id: keyId, revokedAt: null },
    data: { revokedAt: new Date() },
  })
  if (result.count === 0) throw notFound('Active API key')
}

// --------------------------------------------------------------- documents

/** Call the rag-service as this admin, with a freshly minted access token. */
async function asAdmin(
  adminId: string,
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Response> {
  const { timeoutMs = CHECK_TIMEOUT_MS, ...rest } = init
  const { token } = await mintAccessToken(adminId)
  try {
    return await fetch(`${getEnv().RAG_SERVICE_URL}${path}`, {
      ...rest,
      headers: { ...rest.headers, Authorization: `Bearer ${token}` },
      cache: 'no-store',
      signal: AbortSignal.timeout(timeoutMs),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new ApiError('timeout', 'The RAG service took too long to answer')
    }
    throw new ApiError('upstream_unavailable', 'The RAG service is unreachable')
  }
}

const KNOWN_CODES = new Set<string>([
  'unauthorized',
  'forbidden',
  'not_found',
  'invalid_request',
  'conflict',
  'rate_limited',
  'upstream_unavailable',
  'upstream_error',
  'timeout',
])

/** The rag-service's own error, in the same envelope, or a generic one. */
async function upstreamError(res: Response): Promise<ApiError> {
  const body = (await res.json().catch(() => null)) as {
    error?: { code?: string; message?: string }
  } | null
  const code = body?.error?.code
  return new ApiError(
    code && KNOWN_CODES.has(code) ? (code as ApiErrorCode) : 'upstream_error',
    body?.error?.message ?? `The RAG service responded ${res.status}`,
  )
}

async function ragJson(adminId: string, path: string, init?: RequestInit & { timeoutMs?: number }) {
  const res = await asAdmin(adminId, path, init)
  if (!res.ok) throw await upstreamError(res)
  return (await res.json()) as Record<string, unknown>
}

function storeStatus(body: Record<string, unknown> | null): StoreStatus {
  if (!body) return 'unreachable'
  return body['status'] === 'connected' ? 'connected' : 'offline'
}

export async function getDocumentStats(adminId: string): Promise<DocumentStats> {
  const [docs, cache] = await Promise.all([
    ragJson(adminId, '/documents/stats').catch(() => null),
    ragJson(adminId, '/cache/stats').catch(() => null),
  ])
  const count = (body: Record<string, unknown> | null, key: string) =>
    typeof body?.[key] === 'number' ? (body[key] as number) : null
  return {
    index: { status: storeStatus(docs), chunks: count(docs, 'document_count') },
    cache: { status: storeStatus(cache), answers: count(cache, 'keys') },
  }
}

/** Drop every cached answer; returns how many there were. */
export async function clearAnswerCache(adminId: string): Promise<number> {
  const body = await ragJson(adminId, '/cache/clear', { method: 'POST' })
  return typeof body['cleared'] === 'number' ? body['cleared'] : 0
}

/**
 * Remove every document, for every user. Cached answers go too: they were
 * written from documents that no longer exist.
 */
export async function clearDocumentIndex(adminId: string): Promise<{ cacheCleared: number | null }> {
  const body = await ragJson(adminId, '/documents/clear', { method: 'POST' })
  if (body['cleared'] !== true) {
    throw new ApiError('upstream_unavailable', 'The vector store is unreachable; nothing was removed')
  }
  return { cacheCleared: await clearAnswerCache(adminId).catch(() => null) }
}

/** Index one PDF, then drop cached answers so none predates it. */
export async function uploadDocument(adminId: string, file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file, file.name)
  const body = await ragJson(adminId, '/ingest/pdf', {
    method: 'POST',
    body: form,
    timeoutMs: UPLOAD_TIMEOUT_MS,
  })
  return {
    filename: file.name,
    chunks: typeof body['chunks'] === 'number' ? body['chunks'] : 0,
    cacheCleared: await clearAnswerCache(adminId).catch(() => null),
  }
}

// ----------------------------------------------------------- configuration

/** What this instance is configured to do, from the environment. No secrets. */
export function getConfig(): AdminConfig {
  const env = getEnv()
  return {
    publicUrl: env.AUTH_URL ?? null,
    registrationOpen: env.ALLOW_REGISTRATION,
    // Passwords always work; registration only decides who can create one.
    signIn: { password: true, ...oauthProvidersEnabled() },
    defaultModel: env.DEFAULT_MODEL,
    identity: { issuer: env.IDENTITY_ISSUER, audience: env.IDENTITY_AUDIENCE },
    services: { rag: env.RAG_SERVICE_URL, llm: env.LLM_SERVICE_URL },
  }
}
