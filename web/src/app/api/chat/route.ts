import { getChatProvider } from '@/lib/llm'
import { ProviderError } from '@/lib/llm/types'
import { sendMessageSchema } from '@/lib/validations/chat'
import { ApiError, jsonError, parseBody, requireUser, toApiError } from '@/server/http'
import { rateLimit } from '@/server/rate-limit'
import {
  finalizeAssistantMessage,
  prepareTurn,
} from '@/server/services/chat-service'
import type { StreamErrorCode, StreamEvent } from '@/types/chat'

export const runtime = 'nodejs'
// Token generation is inherently uncacheable and must not be pre-rendered.
export const dynamic = 'force-dynamic'

const encoder = new TextEncoder()

function frame(event: StreamEvent): Uint8Array {
  return encoder.encode(`data: ${JSON.stringify(event)}\n\n`)
}

export async function POST(request: Request) {
  // Everything before the stream opens can still fail as a normal JSON error.
  let prepared: Awaited<ReturnType<typeof prepareTurn>>
  try {
    const user = await requireUser()

    const limit = rateLimit(`chat:${user.id}`, 60, 60_000)
    if (!limit.ok) {
      throw new ApiError(
        'rate_limited',
        `Slow down a moment — try again in ${limit.retryAfterSeconds}s.`,
      )
    }

    const input = await parseBody(request, sendMessageSchema)
    prepared = await prepareTurn(user.id, input)
  } catch (error) {
    return jsonError(toApiError(error))
  }

  const provider = getChatProvider()
  const upstream = new AbortController()

  // The browser aborts this request when the user hits Stop or navigates away;
  // propagate that to the model host instead of generating tokens nobody wants.
  request.signal.addEventListener('abort', () => upstream.abort(), { once: true })

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let accumulated = ''
      let closed = false

      const safeEnqueue = (event: StreamEvent) => {
        if (closed) return
        try {
          controller.enqueue(frame(event))
        } catch {
          // The client is gone. Stop writing, but let the loop unwind so the
          // partial answer below still gets persisted.
          closed = true
        }
      }

      safeEnqueue({
        type: 'meta',
        chatId: prepared.chatId,
        title: prepared.title,
        userMessageId: prepared.userMessage.id,
        assistantMessageId: prepared.assistantMessageId,
      })

      let failure: { message: string; code: StreamErrorCode } | null = null

      try {
        for await (const delta of provider.streamCompletion({
          model: prepared.model,
          messages: prepared.providerMessages,
          signal: upstream.signal,
        })) {
          accumulated += delta
          safeEnqueue({ type: 'delta', text: delta })
        }
      } catch (error) {
        if (!request.signal.aborted) {
          const apiError = toApiError(
            error instanceof ProviderError
              ? error
              : new ApiError('upstream_error', 'The model stopped unexpectedly'),
          )
          failure = {
            message: apiError.message,
            code: apiError.code as StreamErrorCode,
          }
        }
      }

      const cancelled = request.signal.aborted || upstream.signal.aborted
      const truncated = cancelled || Boolean(failure)

      try {
        await finalizeAssistantMessage({
          messageId: prepared.assistantMessageId,
          chatId: prepared.chatId,
          content: accumulated,
          model: prepared.model,
          truncated,
          // A stopped generation is a user decision, not an error to flag.
          error: failure && !cancelled ? failure.message : null,
        })
      } catch (error) {
        console.error('[chat] failed to persist assistant message', error)
      }

      if (failure && !cancelled) {
        safeEnqueue({ type: 'error', message: failure.message, code: failure.code })
      } else {
        safeEnqueue({ type: 'done', content: accumulated, truncated })
      }

      closed = true
      try {
        controller.close()
      } catch {
        /* already closed by the client disconnecting */
      }
    },

    cancel() {
      upstream.abort()
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      // Nginx buffers proxied responses by default, which would defeat streaming
      // entirely when this sits behind the gateway.
      'X-Accel-Buffering': 'no',
    },
  })
}
