import { parseSSE } from '@/lib/llm/sse'
import {
  type ChatProvider,
  type CompletionRequest,
  type ProviderModel,
  ProviderError,
} from '@/lib/llm/types'

interface OpenAICompatibleConfig {
  baseUrl: string
  apiKey: string
  timeoutMs: number
}

interface ChatCompletionChunk {
  choices?: Array<{
    delta?: { content?: string | null }
    finish_reason?: string | null
  }>
  error?: { message?: string }
}

interface ModelListResponse {
  data?: Array<{ id?: string; owned_by?: string }>
}

/**
 * Talks to any OpenAI-compatible `/v1` server. In this repo that is
 * `rag-service`, which answers with retrieval-augmented context, but the same
 * adapter works against Ollama's compat layer or a hosted API.
 */
export class OpenAICompatibleProvider implements ChatProvider {
  readonly name = 'openai-compatible'

  constructor(private readonly config: OpenAICompatibleConfig) {}

  async listModels(signal?: AbortSignal): Promise<ProviderModel[]> {
    const response = await this.request('/models', { method: 'GET', signal })
    const payload = (await response.json()) as ModelListResponse

    return (payload.data ?? [])
      .map((entry) => entry.id)
      .filter((id): id is string => typeof id === 'string' && id.length > 0)
      .map((id) => {
        const [head, ...rest] = id.split('/')
        const qualified = rest.length > 0
        return {
          id,
          label: qualified ? rest.join('/') : id,
          provider: qualified ? (head ?? 'local') : 'local',
        }
      })
  }

  async *streamCompletion(request: CompletionRequest): AsyncIterable<string> {
    const response = await this.request('/chat/completions', {
      method: 'POST',
      signal: request.signal,
      body: JSON.stringify({
        model: request.model,
        messages: request.messages.map((message) => ({
          role: message.role,
          content: message.content,
        })),
        stream: true,
        ...(request.temperature === undefined
          ? {}
          : { temperature: request.temperature }),
      }),
    })

    if (!response.body) {
      throw new ProviderError('Upstream returned an empty stream', 'upstream_error')
    }

    for await (const { data } of parseSSE(response.body)) {
      if (data === '[DONE]') return

      let chunk: ChatCompletionChunk
      try {
        chunk = JSON.parse(data) as ChatCompletionChunk
      } catch {
        // A malformed frame is not worth killing a good stream over.
        continue
      }

      if (chunk.error?.message) {
        throw new ProviderError(chunk.error.message, 'upstream_error')
      }

      const text = chunk.choices?.[0]?.delta?.content
      if (typeof text === 'string' && text.length > 0) {
        yield text
      }
    }
  }

  private async request(
    path: string,
    init: { method: string; body?: string; signal?: AbortSignal },
  ): Promise<Response> {
    const timeout = AbortSignal.timeout(this.config.timeoutMs)
    const signal = init.signal
      ? AbortSignal.any([init.signal, timeout])
      : timeout

    let response: Response
    try {
      response = await fetch(`${this.config.baseUrl.replace(/\/$/, '')}${path}`, {
        method: init.method,
        signal,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.config.apiKey}`,
        },
        ...(init.body === undefined ? {} : { body: init.body }),
        cache: 'no-store',
      })
    } catch (error) {
      // Distinguish "the caller hung up" from "the model host is down": only the
      // latter is worth reporting to the user as a failure.
      if (init.signal?.aborted) {
        throw new ProviderError('Request cancelled', 'internal', 499)
      }
      if (error instanceof DOMException && error.name === 'TimeoutError') {
        throw new ProviderError(
          `Model did not respond within ${Math.round(this.config.timeoutMs / 1000)}s`,
          'timeout',
          504,
        )
      }
      throw new ProviderError(
        `Cannot reach the model service at ${this.config.baseUrl}`,
        'upstream_unavailable',
        503,
      )
    }

    if (!response.ok) {
      const detail = await safeErrorText(response)
      throw new ProviderError(
        detail || `Model service responded with ${response.status}`,
        response.status === 429 ? 'rate_limited' : 'upstream_error',
        response.status === 429 ? 429 : 502,
      )
    }

    return response
  }
}

async function safeErrorText(response: Response): Promise<string> {
  try {
    const text = (await response.text()).slice(0, 500)
    try {
      const parsed = JSON.parse(text) as {
        detail?: string | { msg?: string }
        error?: { message?: string } | string
      }
      if (typeof parsed.detail === 'string') return parsed.detail
      if (typeof parsed.detail?.msg === 'string') return parsed.detail.msg
      if (typeof parsed.error === 'string') return parsed.error
      if (typeof parsed.error?.message === 'string') return parsed.error.message
    } catch {
      /* not JSON — fall through to the raw text */
    }
    return text
  } catch {
    return ''
  }
}
