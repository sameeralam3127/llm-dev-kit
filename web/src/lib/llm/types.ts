import type { MessageRole, StreamErrorCode } from '@/types/chat'

export interface ProviderMessage {
  role: MessageRole
  content: string
}

export interface CompletionRequest {
  model: string
  messages: ProviderMessage[]
  signal?: AbortSignal
  temperature?: number
}

export interface ProviderModel {
  id: string
  label: string
  provider: string
}

/**
 * The seam between the app and whatever is generating tokens. Swapping the
 * backend (rag-service, raw Ollama, a hosted API) means writing one of these,
 * not touching routes or UI.
 */
export interface ChatProvider {
  readonly name: string
  listModels(signal?: AbortSignal): Promise<ProviderModel[]>
  streamCompletion(request: CompletionRequest): AsyncIterable<string>
}

export class ProviderError extends Error {
  readonly code: StreamErrorCode
  readonly status: number

  constructor(message: string, code: StreamErrorCode = 'upstream_error', status = 502) {
    super(message)
    this.name = 'ProviderError'
    this.code = code
    this.status = status
  }
}
