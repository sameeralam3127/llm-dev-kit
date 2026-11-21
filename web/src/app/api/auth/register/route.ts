import { NextResponse } from 'next/server'

import { hashPassword, verifyPassword } from '@/lib/auth'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import { registerSchema } from '@/lib/validations/auth'
import { claimFirstAdmin, ensureRolesStarted } from '@/server/identity/admin'
import { ApiError, parseBody, withErrorHandling } from '@/server/http'
import { clientKey, rateLimit } from '@/server/rate-limit'

export const runtime = 'nodejs'

const PUBLIC_USER = { id: true, name: true, email: true, role: true } as const

export const POST = withErrorHandling(async (request: Request) => {
  if (!getEnv().ALLOW_REGISTRATION) {
    throw new ApiError('forbidden', 'Registration is disabled on this instance')
  }

  const limit = rateLimit(clientKey(request, 'register'), 5, 60 * 60 * 1000)
  if (!limit.ok) {
    throw new ApiError(
      'rate_limited',
      `Too many sign-up attempts. Try again in ${limit.retryAfterSeconds}s.`,
    )
  }

  const { name, email, password, setupCode } = await parseBody(request, registerSchema)

  const existing = await db.user.findUnique({
    where: { email },
    select: { id: true, passwordHash: true },
  })
  if (existing) {
    // An account made before the first admin existed is promoted by its own
    // password together with the setup code.
    const proven =
      setupCode !== undefined &&
      existing.passwordHash !== null &&
      (await verifyPassword(password, existing.passwordHash))
    const promoted = proven
      ? await db.$transaction(async (tx) => {
          await ensureRolesStarted(tx)
          if (!(await claimFirstAdmin(setupCode, tx))) return null
          return tx.user.update({
            where: { id: existing.id },
            data: { role: 'admin' },
            select: PUBLIC_USER,
          })
        })
      : null
    if (!promoted) {
      // The address is already discoverable via the sign-in form, so a clear
      // message here costs nothing and saves a confusing dead end.
      throw new ApiError('conflict', 'An account with that email already exists')
    }
    return NextResponse.json({ data: promoted })
  }

  const passwordHash = await hashPassword(password)
  // The setup code is checked in the same transaction that creates the
  // account, so a sign-up that fails spends nothing.
  const user = await db.$transaction(async (tx) => {
    await ensureRolesStarted(tx)
    const admin = await claimFirstAdmin(setupCode, tx)
    return tx.user.create({
      data: { name, email, passwordHash, role: admin ? 'admin' : 'user' },
      select: PUBLIC_USER,
    })
  })

  return NextResponse.json({ data: user }, { status: 201 })
})
