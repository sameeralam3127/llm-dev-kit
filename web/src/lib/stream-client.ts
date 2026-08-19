import { parseSSE } from '@/lib/llm/sse'
import type {
  SendMessagePayload,
  StreamErrorCode,
  StreamEvent,
} from '@/types/chat'

const ERROR_CODES: readonly StreamErrorCode[] = [
  'unauthorized',
  'not_found',
  'rate_limited',
  'upstream_unavailable',
  'upstream_error',
  'timeout',
  'invalid_request',
  'internal',
]

function toErrorCode(value: unknown): StreamErrorCode {
  return ERROR_CODES.includes(value as StreamErrorCode)
    ? (value as StreamErrorCode)
    : 'internal'
}

/**
 * Opens the streaming turn and yields decoded protocol events.
 *
 * Errors that happen before the stream opens arrive as a normal JSON body; once
 * it is open, failures come through as an `error` frame instead, so the caller
 * only ever has to handle one shape.
 */
export async function* streamChat(
  payload: SendMessagePayload,
  signal: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    let code: StreamErrorCode = 'internal'
    try {
      const body = (await response.json()) as {
        error?: { message?: string; code?: string }
      }
      if (body.error?.message) message = body.error.message
      code = toErrorCode(body.error?.code)
    } catch {
      /* non-JSON error body */
    }
    yield { type: 'error', message, code }
    return
  }

  if (!response.body) {
    yield {
      type: 'error',
      message: 'The server returned an empty response',
      code: 'internal',
    }
    return
  }

  for await (const { data } of parseSSE(response.body)) {
    if (!data || data === '[DONE]') continue

    try {
      yield JSON.parse(data) as StreamEvent
    } catch {
      // Ignore unparseable frames rather than aborting a working stream.
    }
  }
}
