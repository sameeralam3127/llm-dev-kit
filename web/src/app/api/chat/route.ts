import { type BackendOptions, backendOptions, getChatProvider, noteModelHost } from '@/lib/llm'
import { ProviderError } from '@/lib/llm/types'
import { serviceErrorMessage } from '@/lib/service-errors'
import { sendMessageSchema } from '@/lib/validations/chat'
import { ApiError, jsonError, parseBody, requireUser, toApiError } from '@/server/http'
import { RATE_LIMITS, rateLimit } from '@/server/rate-limit'
import {
  finalizeAssistantMessage,
  prepareTurn,
} from '@/server/services/chat-service'
import type { MessageSource, StreamErrorCode, StreamEvent } from '@/types/chat'

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
  let backend: BackendOptions
  try {
    const user = await requireUser()

    const limit = rateLimit(`chat:${user.id}`, RATE_LIMITS.chat.limit, RATE_LIMITS.chat.windowMs)
    if (!limit.ok) {
      throw new ApiError(
        'rate_limited',
        `Slow down a moment — try again in ${limit.retryAfterSeconds}s.`,
      )
    }

    const input = await parseBody(request, sendMessageSchema)
    // Before the turn is written: if the backend cannot be reached to set up
    // the user's workspace, nothing half-done is left in the chat.
    backend = await backendOptions(user.id)
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

      let failure: StreamErrorCode | null = null
      let sources: MessageSource[] = []

      try {
        for await (const delta of provider.streamCompletion({
          model: prepared.model,
          messages: prepared.providerMessages,
          signal: upstream.signal,
          onSources: (received) => {
            sources = received
            safeEnqueue({ type: 'sources', sources: received })
          },
          ...backend,
        })) {
          accumulated += delta
          safeEnqueue({ type: 'delta', text: delta })
        }
      } catch (error) {
        if (!request.signal.aborted) {
          failure = error instanceof ProviderError ? error.code : 'upstream_error'
        }
      }

      const cancelled = request.signal.aborted || upstream.signal.aborted
      const truncated = cancelled || Boolean(failure)

      if (!failure && !cancelled) noteModelHost(true)
      else if (failure === 'upstream_unavailable' || failure === 'timeout') noteModelHost(false)

      try {
        await finalizeAssistantMessage({
          messageId: prepared.assistantMessageId,
          chatId: prepared.chatId,
          content: accumulated,
          model: prepared.model,
          truncated,
          sources,
          // A stopped generation is a user decision, not an error to flag.
          errorCode: cancelled ? null : failure,
        })
      } catch {
        console.error('[chat] failed to persist assistant message')
      }

      if (failure && !cancelled) {
        safeEnqueue({ type: 'error', message: serviceErrorMessage(failure), code: failure })
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
