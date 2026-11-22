// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'

import { OpenAICompatibleProvider } from './openai-compatible'
import { ProviderError } from './types'

const chunk = (content: string) =>
  `data: ${JSON.stringify({ choices: [{ delta: { content }, finish_reason: null }] })}\n\n`

function serve(...frames: string[]) {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) controller.enqueue(new TextEncoder().encode(frame))
      controller.close()
    },
  })
  vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200 })))
}

async function collect() {
  const provider = new OpenAICompatibleProvider({ baseUrl: 'http://rag.test/v1', timeoutMs: 5000 })
  const parts: string[] = []
  for await (const part of provider.streamCompletion({
    model: 'llama3.1',
    messages: [{ role: 'user', content: 'hi' }],
  })) {
    parts.push(part)
  }
  return parts.join('')
}

afterEach(() => vi.unstubAllGlobals())

describe('OpenAI-compatible streams', () => {
  it('return the answer when the stream finishes with [DONE]', async () => {
    serve(chunk('grounded '), chunk('answer'), 'data: [DONE]\n\n')
    await expect(collect()).resolves.toBe('grounded answer')
  })

  it('fail on an error event, so the answer is stored as failed', async () => {
    serve(chunk('grounded '), `data: ${JSON.stringify({ error: { message: 'model crashed' } })}\n\n`)
    await expect(collect()).rejects.toThrow(new ProviderError('model crashed', 'upstream_error'))
  })

  it('fail when the stream stops before [DONE], instead of keeping half an answer', async () => {
    serve(chunk('grounded '))
    await expect(collect()).rejects.toThrow(/ended before/)
  })
})
