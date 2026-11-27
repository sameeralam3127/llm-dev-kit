import 'server-only'

import type { Prisma } from '@prisma/client'

import { hashSetupCode, SETUP_ID } from '../../../prisma/setup-code.mjs'

async function hasAdmin(client: Prisma.TransactionClient): Promise<boolean> {
  return Boolean(await client.user.findFirst({ where: { role: 'admin' }, select: { id: true } }))
}

/**
 * Creates the setup row the first time roles are used. Its presence marks a
 * database that has been through this code. A database that predates roles
 * (users, no admin, no row) gets its earliest user promoted, once.
 */
export async function ensureRolesStarted(client: Prisma.TransactionClient): Promise<void> {
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
 * Spends the setup code if it is valid for the email and no admin exists yet,
 * returning whether the caller may make its account an admin. Call it inside
 * the transaction that creates or promotes the account, so a failure rolls the
 * code back too.
 */
export async function claimFirstAdmin(
  code: string,
  email: string,
  client: Prisma.TransactionClient,
): Promise<boolean> {
  if (await hasAdmin(client)) return false
  const { count } = await client.setupCode.updateMany({
    where: { id: SETUP_ID, hash: await hashSetupCode(code, email), expiresAt: { gt: new Date() } },
    data: { hash: null, expiresAt: null },
  })
  return count === 1
}
