import { parseSSE } from '@/lib/llm/sse'
import { parseSources } from '@/lib/sources'
import {
  type ChatProvider,
  type CompletionRequest,
  type ListModelsOptions,
  type ProviderModel,
  ProviderError,
} from '@/lib/llm/types'

interface OpenAICompatibleConfig {
  baseUrl: string
  /** A static key for third-party backends; a per-call `authorization` wins. */
  apiKey?: string
  timeoutMs: number
}

interface ChatCompletionChunk {
  choices?: Array<{
    delta?: { content?: string | null }
    finish_reason?: string | null
  }>
  error?: unknown
  /** Not OpenAI: this repo's backends attach the retrieved passages here. */
  citations?: unknown
}

interface ModelListResponse {
  data?: Array<{ id?: string; owned_by?: string }>
}

/**
 * Talks to any OpenAI-compatible `/v1` server. In this repo that is
 * `rag-service`, or core-api in the lite profile, both of which answer with
 * retrieval-augmented context; the same adapter works against Ollama's compat
 * layer or a hosted API.
 */
export class OpenAICompatibleProvider implements ChatProvider {
  readonly name = 'openai-compatible'

  constructor(private readonly config: OpenAICompatibleConfig) {}

  async listModels(options: ListModelsOptions = {}): Promise<ProviderModel[]> {
    const response = await this.request('/models', {
      method: 'GET',
      ...(options.signal ? { signal: options.signal } : {}),
      ...(options.authorization ? { authorization: options.authorization } : {}),
      ...(options.workspaceId ? { workspaceId: options.workspaceId } : {}),
    })
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
      ...(request.signal ? { signal: request.signal } : {}),
      ...(request.authorization ? { authorization: request.authorization } : {}),
      ...(request.workspaceId ? { workspaceId: request.workspaceId } : {}),
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
      throw new ProviderError()
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

      if (chunk?.error) {
        throw new ProviderError()
      }

      if (chunk?.citations !== undefined && request.onSources) {
        const sources = parseSources(chunk.citations)
        if (sources.length > 0) request.onSources(sources)
      }

      const text = chunk?.choices?.[0]?.delta?.content
      if (typeof text === 'string' && text.length > 0) {
        yield text
      }
    }

    // OpenAI-compatible servers end a finished answer with [DONE]. Without it
    // the answer was cut off, and must not be stored as complete.
    throw new ProviderError()
  }

  private async request(
    path: string,
    init: {
      method: string
      body?: string
      signal?: AbortSignal
      authorization?: string
      workspaceId?: string
    },
  ): Promise<Response> {
    const credential = init.authorization ?? this.config.apiKey
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
          ...(credential ? { Authorization: `Bearer ${credential}` } : {}),
          ...(init.workspaceId ? { 'X-Workspace-Id': init.workspaceId } : {}),
        },
        ...(init.body === undefined ? {} : { body: init.body }),
        cache: 'no-store',
      })
    } catch (error) {
      // Distinguish "the caller hung up" from "the model host is down": only the
      // latter is worth reporting to the user as a failure.
      if (init.signal?.aborted) {
        throw new ProviderError('internal', 499)
      }
      if (error instanceof DOMException && error.name === 'TimeoutError') {
        throw new ProviderError('timeout', 504)
      }
      throw new ProviderError('upstream_unavailable', 503)
    }

    if (!response.ok) {
      // The response body can contain request content or internal provider details.
      await response.body?.cancel().catch(() => undefined)
      throw response.status === 429 ? new ProviderError('rate_limited', 429) : new ProviderError()
    }

    return response
  }
}
