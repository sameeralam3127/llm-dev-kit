// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'

import { OpenAICompatibleProvider } from './openai-compatible'

const ERROR_CANARY = 'synthetic-provider-diagnostic'

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

async function collect(baseUrl = 'http://rag.test/v1') {
  const provider = new OpenAICompatibleProvider({ baseUrl, timeoutMs: 5000 })
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

  it('fail on an error event with an app-owned message', async () => {
    serve(chunk('grounded '), `data: ${JSON.stringify({ error: { message: ERROR_CANARY } })}\n\n`)
    await expect(collect()).rejects.toMatchObject({
      code: 'upstream_error',
      message: 'The upstream service could not complete the request',
    })
  })

  it('fail when the stream stops before [DONE], instead of keeping half an answer', async () => {
    serve(chunk('grounded '))
    await expect(collect()).rejects.toMatchObject({ code: 'upstream_error' })
  })
})

describe('upstream model request failures', () => {
  it.each([
    [500, 'upstream_error', 502, 'The upstream service could not complete the request'],
    [429, 'rate_limited', 429, 'The service is receiving too many requests. Try again shortly.'],
  ])('maps HTTP %i by status without reading its body', async (status, code, publicStatus, message) => {
    const response = Response.json({ error: { message: ERROR_CANARY } }, { status })
    const text = vi.spyOn(response, 'text')
    const json = vi.spyOn(response, 'json')
    vi.stubGlobal('fetch', vi.fn(async () => response))

    await expect(collect()).rejects.toMatchObject({ code, status: publicStatus, message })
    expect(text).not.toHaveBeenCalled()
    expect(json).not.toHaveBeenCalled()
  })

  it('omits configured URLs and transport diagnostics when the service is down', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new Error(ERROR_CANARY)
    }))
    await expect(collect('http://internal-model.test/v1')).rejects.toMatchObject({
      code: 'upstream_unavailable',
      message: 'The upstream service is unreachable',
    })
  })
})

describe('acting in a workspace', () => {
  it('sends X-Workspace-Id on chat and model calls when given one', async () => {
    const seen: Array<string | null> = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init: RequestInit) => {
        seen.push(new Headers(init.headers).get('x-workspace-id'))
        if (url.endsWith('/models')) return new Response(JSON.stringify({ data: [{ id: 'llama3.1' }] }))
        return new Response(chunk('ok') + 'data: [DONE]\n\n')
      }),
    )
    const provider = new OpenAICompatibleProvider({ baseUrl: 'http://core.test/v1', timeoutMs: 5000 })
    await provider.listModels({ authorization: 't', workspaceId: 'ws-1' })
    for await (const _ of provider.streamCompletion({
      model: 'llama3.1',
      messages: [{ role: 'user', content: 'hi' }],
      authorization: 't',
      workspaceId: 'ws-1',
    })) {
      // drain
    }
    await provider.listModels({ authorization: 't' })
    expect(seen).toEqual(['ws-1', 'ws-1', null])
  })
})
