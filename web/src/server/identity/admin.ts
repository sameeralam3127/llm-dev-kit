import 'server-only'

import { createHash, randomBytes } from 'node:crypto'

import type { Prisma } from '@prisma/client'

import { db } from '@/lib/db'

type Client = Prisma.TransactionClient | typeof db

const SETUP_ID = 'instance'

export function hashSetupCode(code: string): string {
  return createHash('sha256').update(code).digest('hex')
}

async function hasAdmin(client: Client): Promise<boolean> {
  return Boolean(await client.user.findFirst({ where: { role: 'admin' }, select: { id: true } }))
}

/**
 * Creates the setup row the first time roles are used. Its presence marks a
 * database that has been through this code. A database that predates roles
 * (users, no admin, no row) gets its earliest user promoted, once.
 */
export async function ensureRolesStarted(client: Client): Promise<void> {
  const row = await client.setupCode.findUnique({ where: { id: SETUP_ID }, select: { id: true } })
  if (row) return

  if (!(await hasAdmin(client))) {
    const first = await client.user.findFirst({
      orderBy: [{ createdAt: 'asc' }, { id: 'asc' }],
      select: { id: true },
    })
    if (first) await client.user.update({ where: { id: first.id }, data: { role: 'admin' } })
  }
  await client.setupCode.create({ data: { id: SETUP_ID, hash: null } })
}

/**
 * Runs at server start. While the instance has no admin, issues a fresh
 * one-time setup code and returns it for the operator to read in the log. A
 * restart replaces any earlier code, so a lost log is recovered by restarting.
 */
export async function bootstrapAdmin(client: Client = db): Promise<string | null> {
  await ensureRolesStarted(client)
  if (await hasAdmin(client)) return null

  const code = randomBytes(24).toString('base64url')
  await client.setupCode.update({ where: { id: SETUP_ID }, data: { hash: hashSetupCode(code) } })
  return code
}

/**
 * Spends the setup code if it is the one issued and no admin exists yet,
 * returning whether the caller may make its account an admin. Call it inside
 * the transaction that creates or promotes the account, so a failure rolls the
 * code back too.
 */
export async function claimFirstAdmin(code: string | undefined, client: Client = db): Promise<boolean> {
  if (!code) return false
  if (await hasAdmin(client)) return false
  const { count } = await client.setupCode.updateMany({
    where: { id: SETUP_ID, hash: hashSetupCode(code) },
    data: { hash: null },
  })
  return count === 1
}
