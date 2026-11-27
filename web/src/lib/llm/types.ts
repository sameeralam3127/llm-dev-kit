import { serviceErrorMessage } from '@/lib/service-errors'
import type { MessageRole, MessageSource, StreamErrorCode } from '@/types/chat'

export interface ProviderMessage {
  role: MessageRole
  content: string
}

export interface CompletionRequest {
  model: string
  messages: ProviderMessage[]
  signal?: AbortSignal
  temperature?: number
  /** Bearer credential for this call: the user's access token. */
  authorization?: string
  /** core-api's workspace to act in, sent as X-Workspace-Id. */
  workspaceId?: string
  /** Called when the backend reports which passages it answered from. */
  onSources?: (sources: MessageSource[]) => void
}

export interface ListModelsOptions {
  signal?: AbortSignal
  authorization?: string
  workspaceId?: string
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
  listModels(options?: ListModelsOptions): Promise<ProviderModel[]>
  streamCompletion(request: CompletionRequest): AsyncIterable<string>
}

export class ProviderError extends Error {
  readonly code: StreamErrorCode
  readonly status: number

  constructor(code: StreamErrorCode = 'upstream_error', status = 502) {
    super(serviceErrorMessage(code))
    this.name = 'ProviderError'
    this.code = code
    this.status = status
  }
}
