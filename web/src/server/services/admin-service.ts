import 'server-only'

import { oauthProvidersEnabled } from '@/lib/auth'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import { asRole, type Role } from '@/lib/roles'
import { type Actor, recordAudit } from '@/server/audit'
import { RATE_LIMITS } from '@/server/rate-limit'
import { plural } from '@/lib/utils'
import { ApiError, type ApiErrorCode, notFound } from '@/server/http'
import { mintAccessToken } from '@/server/identity/tokens'
import type {
  ActivityDay,
  AdminApiKey,
  AdminConfig,
  AdminHealth,
  AdminOverview,
  AdminPlugin,
  AdminUsageRow,
  AdminUser,
  DocumentStats,
  HealthCheck,
  IngestionJobDTO,
  PluginInventory,
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
export async function setUserRole(actor: Actor, userId: string, role: Role): Promise<AdminUser> {
  await db.$transaction(async (tx) => {
    const target = await tx.user.findUnique({
      where: { id: userId },
      select: { role: true, email: true },
    })
    if (!target) throw notFound('User')

    if (asRole(target.role) === 'admin' && role !== 'admin') {
      const admins = await tx.user.count({ where: { role: 'admin' } })
      if (admins <= 1) {
        throw new ApiError('conflict', 'There must be at least one admin; promote someone else first')
      }
    }
    await tx.user.update({ where: { id: userId }, data: { role } })

    // Committed with the change itself: no role change without its entry.
    const from = asRole(target.role)
    if (from !== role) {
      await recordAudit(
        actor,
        {
          action: 'user.role_changed',
          target: `user:${userId}`,
          detail: { email: target.email, from, to: role },
        },
        tx,
      )
    }
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
        ? { name: 'Document index', status: 'ok', detail: `${plural(Number(docsBody['document_count']), 'chunk')} indexed` }
        : { name: 'Document index', status: 'down', detail: 'Vector store unreachable' },
    !cacheBody
      ? { name: 'Answer cache', status: 'down', detail: unreadable(cache) }
      : cacheBody['status'] === 'connected'
        ? { name: 'Answer cache', status: 'ok', detail: `${plural(Number(cacheBody['keys'] ?? 0), 'cached answer')}` }
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

  const [users, admins, chats, messages, sharedChats, apiKeys, recent, questions, newChats, usage] =
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
      usageByUserAndModel(),
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
    usage,
  }
}

/** Rows shown in the usage table: enough to spot heavy use, bounded for any instance size. */
export const USAGE_ROWS = 50

export interface UsageQueryRow {
  userId: string
  name: string | null
  email: string
  model: string
  /** SQLite returns numbers; Postgres returns bigints for COUNT. */
  chats: number | bigint
  messages: number | bigint
}

/** Shape the grouped rows for the API. */
export function toUsageRows(rows: UsageQueryRow[]): AdminUsageRow[] {
  return rows.map((row) => ({
    userId: row.userId,
    user: row.name ?? row.email,
    email: row.email,
    model: row.model,
    chats: Number(row.chats),
    messages: Number(row.messages),
  }))
}

/**
 * Chats and messages per user and model, grouped and sorted in the database,
 * so the cost does not grow with the number of chats held in memory.
 */
async function usageByUserAndModel(): Promise<AdminUsageRow[]> {
  const rows = await db.$queryRaw<UsageQueryRow[]>`
    SELECT c."userId" AS "userId", u."name" AS "name", u."email" AS "email",
           c."model" AS "model",
           COUNT(DISTINCT c."id") AS "chats", COUNT(m."id") AS "messages"
    FROM "Chat" c
    JOIN "User" u ON u."id" = c."userId"
    LEFT JOIN "Message" m ON m."chatId" = c."id"
    GROUP BY c."userId", u."name", u."email", c."model"
    ORDER BY "messages" DESC, u."email" ASC, c."model" ASC
    LIMIT ${USAGE_ROWS}`
  return toUsageRows(rows)
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
export async function revokeAnyApiKey(actor: Actor, keyId: string): Promise<void> {
  const key = await db.apiKey.findUnique({
    where: { id: keyId },
    select: { name: true, prefix: true, user: { select: { email: true } } },
  })
  const result = await db.apiKey.updateMany({
    where: { id: keyId, revokedAt: null },
    data: { revokedAt: new Date() },
  })
  if (result.count === 0) throw notFound('Active API key')
  await recordAudit(actor, {
    action: 'api_key.revoked',
    target: `api_key:${keyId}`,
    detail: { name: key?.name, prefix: key?.prefix, owner: key?.user.email },
  })
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

/** Drop every cached answer without a record: callers that already audit a bigger action use this. */
async function dropCachedAnswers(adminId: string): Promise<number> {
  const body = await ragJson(adminId, '/cache/clear', { method: 'POST' })
  return typeof body['cleared'] === 'number' ? body['cleared'] : 0
}

/** Drop every cached answer; returns how many there were. */
export async function clearAnswerCache(actor: Actor): Promise<number> {
  const cleared = await dropCachedAnswers(actor.id)
  await recordAudit(actor, { action: 'cache.cleared', detail: { cleared } })
  return cleared
}

/**
 * Remove every document, for every user. Cached answers go too: they were
 * written from documents that no longer exist.
 */
export async function clearDocumentIndex(actor: Actor): Promise<{ cacheCleared: number | null }> {
  const body = await ragJson(actor.id, '/documents/clear', { method: 'POST' })
  if (body['cleared'] !== true) {
    throw new ApiError('upstream_unavailable', 'The vector store is unreachable; nothing was removed')
  }
  const cacheCleared = await dropCachedAnswers(actor.id).catch(() => null)
  await recordAudit(actor, { action: 'document.index_cleared', detail: { cacheCleared } })
  return { cacheCleared }
}

/**
 * Index one PDF, then drop cached answers so none predates it. The upload is
 * recorded as a job from start to finish, and as an audit entry either way.
 */
export async function uploadDocument(actor: Actor, file: File): Promise<UploadResult> {
  const job = await db.ingestionJob.create({
    data: { uploadedBy: actor.email, filename: file.name, sizeBytes: file.size, status: 'running' },
    select: { id: true },
  })
  const form = new FormData()
  form.append('file', file, file.name)
  try {
    const body = await ragJson(actor.id, '/ingest/pdf', {
      method: 'POST',
      body: form,
      timeoutMs: UPLOAD_TIMEOUT_MS,
    })
    const chunks = typeof body['chunks'] === 'number' ? body['chunks'] : 0
    const cacheCleared = await dropCachedAnswers(actor.id).catch(() => null)
    await db.ingestionJob.update({
      where: { id: job.id },
      data: { status: 'succeeded', chunks, finishedAt: new Date() },
    })
    await recordAudit(actor, {
      action: 'document.uploaded',
      target: file.name,
      detail: { bytes: file.size, chunks },
    })
    return { filename: file.name, chunks, cacheCleared }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Upload failed'
    await db.ingestionJob.update({
      where: { id: job.id },
      data: { status: 'failed', error: message.slice(0, 500), finishedAt: new Date() },
    })
    await recordAudit(actor, {
      action: 'document.upload_failed',
      target: file.name,
      detail: { bytes: file.size, error: message.slice(0, 200) },
    })
    throw error
  }
}

/** A "running" job older than this outlived any possible upload: the web app restarted mid-way. */
const INTERRUPTED_AFTER_MS = UPLOAD_TIMEOUT_MS + 60_000

/** The most recent console uploads, newest first. */
export async function listIngestionJobs(limit = 20): Promise<IngestionJobDTO[]> {
  const rows = await db.ingestionJob.findMany({ orderBy: { startedAt: 'desc' }, take: limit })
  const now = Date.now()
  return rows.map((row) => ({
    id: row.id,
    filename: row.filename,
    sizeBytes: row.sizeBytes,
    status:
      row.status === 'running' && now - row.startedAt.getTime() > INTERRUPTED_AFTER_MS
        ? 'interrupted'
        : (row.status as IngestionJobDTO['status']),
    chunks: row.chunks,
    error: row.error,
    startedAt: row.startedAt.toISOString(),
    finishedAt: row.finishedAt?.toISOString() ?? null,
    uploadedBy: row.uploadedBy,
  }))
}

// ----------------------------------------------------------------- plugins

/**
 * What each Python service has installed, from its own plugin registry.
 * Read-only: a toggle would apply to one replica and be lost on restart.
 */
export async function getPluginInventory(actor: Actor): Promise<PluginInventory> {
  const env = getEnv()
  const { token } = await mintAccessToken(actor.id)
  const services = [
    { name: 'llm-service', url: env.LLM_SERVICE_URL },
    { name: 'rag-service', url: env.RAG_SERVICE_URL },
  ] as const

  const results = await Promise.all(
    services.map(async ({ name, url }) => {
      const res = await probe(`${url}/plugins`, { headers: { Authorization: `Bearer ${token}` } })
      const body = res?.ok ? ((await res.json().catch(() => null)) as unknown) : null
      if (!Array.isArray(body)) return { name, plugins: null }
      return { name, plugins: body.map((row) => toPlugin(name, row as Record<string, unknown>)) }
    }),
  )

  return {
    plugins: results.flatMap((result) => result.plugins ?? []),
    unreachable: results.filter((result) => result.plugins === null).map((result) => result.name),
  }
}

function toPlugin(service: AdminPlugin['service'], row: Record<string, unknown>): AdminPlugin {
  return {
    service,
    kind: String(row['kind'] ?? ''),
    name: String(row['name'] ?? ''),
    version: String(row['version'] ?? ''),
    enabled: row['enabled'] === true,
    description: String(row['description'] ?? ''),
    permissions: Array.isArray(row['permissions']) ? row['permissions'].map(String) : [],
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
    rateLimits: [
      { name: 'Sign-up', ...rateLimitView(RATE_LIMITS.register) },
      { name: 'Chat messages', ...rateLimitView(RATE_LIMITS.chat) },
      { name: 'API key exchange', ...rateLimitView(RATE_LIMITS.tokenExchange) },
    ],
    dashboardUrl: env.GRAFANA_URL || null,
  }
}

function rateLimitView(rule: { limit: number; windowMs: number; per: string }) {
  return { limit: rule.limit, windowSeconds: rule.windowMs / 1000, per: rule.per }
}
