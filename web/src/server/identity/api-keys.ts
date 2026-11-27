import 'server-only'

import { createHash, randomBytes } from 'node:crypto'

import { db } from '@/lib/db'
import { ApiError, notFound } from '@/server/http'
import type { ApiKeySummary, CreatedApiKey } from '@/types/api-key'

export const API_KEY_PREFIX = 'sk-ldk-'
const PREFIX_SHOWN = API_KEY_PREFIX.length + 4
const MAX_ACTIVE_KEYS = 20
/** lastUsedAt is written at most this often per key. */
const TOUCH_AFTER_MS = 60_000

/**
 * Digest a server-generated token with 32 random bytes for indexed lookup.
 * The local Python auth plugin uses the same digest to verify these keys.
 */
export function hashApiKey(key: string): string {
  return createHash('sha256').update(key).digest('hex')
}

function summary(row: {
  id: string
  name: string
  prefix: string
  createdAt: Date
  lastUsedAt: Date | null
}): ApiKeySummary {
  return {
    id: row.id,
    name: row.name,
    prefix: row.prefix,
    createdAt: row.createdAt.toISOString(),
    lastUsedAt: row.lastUsedAt?.toISOString() ?? null,
  }
}

const SUMMARY = { id: true, name: true, prefix: true, createdAt: true, lastUsedAt: true } as const

export async function listApiKeys(userId: string): Promise<ApiKeySummary[]> {
  const rows = await db.apiKey.findMany({
    where: { userId, revokedAt: null },
    orderBy: { createdAt: 'desc' },
    select: SUMMARY,
  })
  return rows.map(summary)
}

/** Create a key. The returned `key` is the only time it is ever visible. */
export async function createApiKey(
  userId: string,
  name: string,
): Promise<CreatedApiKey> {
  const active = await db.apiKey.count({ where: { userId, revokedAt: null } })
  if (active >= MAX_ACTIVE_KEYS) {
    throw new ApiError('conflict', `You can have at most ${MAX_ACTIVE_KEYS} keys; revoke one first`)
  }

  const key = `${API_KEY_PREFIX}${randomBytes(32).toString('base64url')}`
  const row = await db.apiKey.create({
    data: { userId, name, prefix: key.slice(0, PREFIX_SHOWN), hash: hashApiKey(key) },
    select: SUMMARY,
  })
  return { ...summary(row), key }
}

export async function revokeApiKey(userId: string, keyId: string): Promise<void> {
  const result = await db.apiKey.updateMany({
    where: { id: keyId, userId, revokedAt: null },
    data: { revokedAt: new Date() },
  })
  if (result.count === 0) throw notFound('API key')
}

/** The owner of a valid, unrevoked key, or null. */
export async function resolveApiKey(key: string): Promise<string | null> {
  if (!key.startsWith(API_KEY_PREFIX)) return null
  const row = await db.apiKey.findUnique({
    where: { hash: hashApiKey(key) },
    select: { id: true, userId: true, revokedAt: true, lastUsedAt: true },
  })
  if (!row || row.revokedAt) return null

  const now = Date.now()
  if (!row.lastUsedAt || now - row.lastUsedAt.getTime() > TOUCH_AFTER_MS) {
    await db.apiKey.update({ where: { id: row.id }, data: { lastUsedAt: new Date(now) } })
  }
  return row.userId
}
