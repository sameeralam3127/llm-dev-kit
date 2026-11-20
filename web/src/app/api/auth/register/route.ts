import { NextResponse } from 'next/server'

import { hashPassword } from '@/lib/auth'
import { db } from '@/lib/db'
import { getEnv } from '@/lib/env'
import { registerSchema } from '@/lib/validations/auth'
import { ensureAdmin } from '@/server/identity/admin'
import { ApiError, parseBody, withErrorHandling } from '@/server/http'
import { clientKey, RATE_LIMITS, rateLimit } from '@/server/rate-limit'

export const runtime = 'nodejs'

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

  const { name, email, password } = await parseBody(request, registerSchema)

  const existing = await db.user.findUnique({
    where: { email },
    select: { id: true },
  })
  if (existing) {
    // The address is already discoverable via the sign-in form, so a clear
    // message here costs nothing and saves a confusing dead end.
    throw new ApiError('conflict', 'An account with that email already exists')
  }

  const passwordHash = await hashPassword(password)
  // The first account becomes the admin in the same transaction that creates
  // it, so there is never a moment with users but no admin.
  const user = await db.$transaction(async (tx) => {
    const created = await tx.user.create({
      data: { name, email, passwordHash },
      select: { id: true },
    })
    await ensureAdmin(tx)
    return tx.user.findUniqueOrThrow({
      where: { id: created.id },
      select: { id: true, name: true, email: true, role: true },
    })
  })

  return NextResponse.json({ data: user }, { status: 201 })
})
