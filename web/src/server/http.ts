import 'server-only'

import { NextResponse } from 'next/server'
import { ZodError, type ZodType, type ZodTypeDef } from 'zod'

import { auth } from '@/lib/auth'
import { ProviderError } from '@/lib/llm/types'

export type ApiErrorCode =
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'invalid_request'
  | 'conflict'
  | 'rate_limited'
  | 'upstream_unavailable'
  | 'upstream_error'
  | 'timeout'
  | 'internal'

const STATUS_BY_CODE: Record<ApiErrorCode, number> = {
  unauthorized: 401,
  forbidden: 403,
  not_found: 404,
  invalid_request: 400,
  conflict: 409,
  rate_limited: 429,
  upstream_unavailable: 503,
  upstream_error: 502,
  timeout: 504,
  internal: 500,
}

export class ApiError extends Error {
  readonly code: ApiErrorCode
  readonly details?: unknown

  constructor(code: ApiErrorCode, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = details
  }

  get status(): number {
    return STATUS_BY_CODE[this.code]
  }
}

export const notFound = (what = 'Resource') =>
  new ApiError('not_found', `${what} not found`)

export const badRequest = (message: string, details?: unknown) =>
  new ApiError('invalid_request', message, details)

export function jsonError(error: ApiError): NextResponse {
  return NextResponse.json(
    {
      error: {
        code: error.code,
        message: error.message,
        ...(error.details === undefined ? {} : { details: error.details }),
      },
    },
    { status: error.status },
  )
}

/**
 * One place that turns anything thrown inside a route into a response, so no
 * handler leaks a stack trace and every failure has the same shape.
 */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  if (error instanceof ZodError) {
    return new ApiError(
      'invalid_request',
      'Request validation failed',
      error.issues.map((issue) => ({
        path: issue.path.join('.'),
        message: issue.message,
      })),
    )
  }

  if (error instanceof ProviderError) {
    return new ApiError(error.code as ApiErrorCode, error.message)
  }

  if (process.env.NODE_ENV !== 'production') {
    console.error('[api] unhandled error', error)
  }

  return new ApiError('internal', 'Something went wrong on our end')
}

/** Wraps a handler so thrown ApiErrors become responses. */
export function withErrorHandling<Args extends unknown[]>(
  handler: (...args: Args) => Promise<NextResponse>,
): (...args: Args) => Promise<NextResponse> {
  return async (...args: Args) => {
    try {
      return await handler(...args)
    } catch (error) {
      return jsonError(toApiError(error))
    }
  }
}

export interface SessionUser {
  id: string
  email: string
  name: string | null
  image: string | null
}

/** Throws rather than returning null so handlers can stay linear. */
export async function requireUser(): Promise<SessionUser> {
  const session = await auth()
  const user = session?.user

  if (!user?.id) {
    throw new ApiError('unauthorized', 'Sign in to continue')
  }

  return {
    id: user.id,
    email: user.email ?? '',
    name: user.name ?? null,
    image: user.image ?? null,
  }
}

/**
 * Input is `unknown` rather than `T`: schemas here transform (query strings to
 * booleans, emails to lower case), so the parsed output type is not the same as
 * what goes in.
 */
type AnySchema<T> = ZodType<T, ZodTypeDef, unknown>

export async function parseBody<T>(
  request: Request,
  schema: AnySchema<T>,
): Promise<T> {
  let raw: unknown
  try {
    raw = await request.json()
  } catch {
    throw badRequest('Request body must be valid JSON')
  }
  return schema.parse(raw)
}

export function parseQuery<T>(request: Request, schema: AnySchema<T>): T {
  const params = Object.fromEntries(new URL(request.url).searchParams.entries())
  return schema.parse(params)
}
