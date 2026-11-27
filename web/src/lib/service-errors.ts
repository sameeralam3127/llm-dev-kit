import type { StreamErrorCode } from '@/types/chat'

const SERVICE_ERROR_MESSAGES = {
  unauthorized: 'The service could not authenticate the request',
  forbidden: 'The service denied the request',
  not_found: 'The requested resource was not found',
  invalid_request: 'The service could not process the request',
  conflict: 'The request conflicts with the current state',
  rate_limited: 'The service is receiving too many requests. Try again shortly.',
  upstream_unavailable: 'The upstream service is unreachable',
  upstream_error: 'The upstream service could not complete the request',
  timeout: 'The upstream service took too long to respond',
  internal: 'Something went wrong on our end',
} satisfies Record<StreamErrorCode | 'forbidden' | 'conflict', string>

export type ServiceErrorCode = keyof typeof SERVICE_ERROR_MESSAGES

export function isServiceErrorCode(code: unknown): code is ServiceErrorCode {
  return typeof code === 'string' && Object.hasOwn(SERVICE_ERROR_MESSAGES, code)
}

/** Resolve only known codes. Older stored error text gets a generic message. */
export function serviceErrorMessage(code: unknown): string {
  return SERVICE_ERROR_MESSAGES[isServiceErrorCode(code) ? code : 'upstream_error']
}
