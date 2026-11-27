import { NextResponse } from 'next/server'

import { hashPassword, verifyPassword } from '@/lib/auth'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import { registerSchema } from '@/lib/validations/auth'
import { claimFirstAdmin, ensureRolesStarted } from '@/server/identity/admin'
import { ApiError, parseBody, withErrorHandling } from '@/server/http'
import { clientKey, RATE_LIMITS, rateLimit } from '@/server/rate-limit'

export const runtime = 'nodejs'

const PUBLIC_USER = { id: true, name: true, email: true, role: true } as const

export const POST = withErrorHandling(async (request: Request) => {
  if (!getEnv().ALLOW_REGISTRATION) {
    throw new ApiError('forbidden', 'Registration is disabled on this instance')
  }

  const limit = rateLimit(
    clientKey(request, 'register'),
    RATE_LIMITS.register.limit,
    RATE_LIMITS.register.windowMs,
  )
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
    if (setupCode && existing.passwordHash && (await verifyPassword(password, existing.passwordHash))) {
      const promoted = await db.$transaction(async (tx) => {
        await ensureRolesStarted(tx)
        if (!(await claimFirstAdmin(setupCode, email, tx))) return null
        return tx.user.update({
          where: { id: existing.id },
          data: { role: 'admin' },
          select: PUBLIC_USER,
        })
      })
      if (promoted) return NextResponse.json({ data: promoted })
    }
    if (setupCode) throw new ApiError('forbidden', 'Could not use that setup code for this account')
    throw new ApiError('conflict', 'An account with that email already exists')
  }

  const passwordHash = await hashPassword(password)
  // The setup code is checked in the same transaction that creates the
  // account, so a sign-up that fails spends nothing.
  const user = await db.$transaction(async (tx) => {
    await ensureRolesStarted(tx)
    if (setupCode && !(await claimFirstAdmin(setupCode, email, tx))) {
      throw new ApiError('forbidden', 'Could not use that setup code for this account')
    }
    return tx.user.create({
      data: { name, email, passwordHash, role: setupCode ? 'admin' : 'user' },
      select: PUBLIC_USER,
    })
  })

  return NextResponse.json({ data: user }, { status: 201 })
})
