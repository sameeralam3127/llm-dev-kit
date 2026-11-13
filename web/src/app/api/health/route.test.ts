/// <reference types="vitest/globals" />
// @vitest-environment node
import { describe, expect, it, vi } from 'vitest'

const queryRaw = vi.hoisted(() => vi.fn())

vi.mock('@/lib/db', () => ({
  db: { $queryRaw: queryRaw },
}))

import { GET } from './route'

describe('GET /api/health', () => {
  it('returns ok when the database responds', async () => {
    queryRaw.mockResolvedValueOnce([{ 1: 1 }])

    const response = await GET()

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ status: 'ok' })
    expect(queryRaw).toHaveBeenCalledOnce()
  })

  it('returns service unavailable when the database probe fails', async () => {
    queryRaw.mockRejectedValueOnce(new Error('database unavailable'))

    const response = await GET()

    expect(response.status).toBe(503)
    expect(await response.json()).toEqual({ status: 'unavailable' })
  })
})
