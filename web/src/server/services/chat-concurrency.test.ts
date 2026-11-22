// @vitest-environment node
import { execFileSync } from 'node:child_process'
import { rmSync } from 'node:fs'

import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

// A real SQLite file, because the failure lives in SQLite's locking, which a
// mocked client cannot show.
const dir = vi.hoisted(() => {
  const { mkdtempSync } = require('node:fs') as typeof import('node:fs')
  const { tmpdir } = require('node:os') as typeof import('node:os')
  const { join } = require('node:path') as typeof import('node:path')
  const created = mkdtempSync(join(tmpdir(), 'ldk-chat-'))
  process.env.DATABASE_URL = `file:${join(created, 'test.db')}`
  return created
})

vi.mock('@/lib/env', () => ({ getEnv: () => ({ DEFAULT_MODEL: 'llama3.1' }) }))
vi.mock('@/server/http', () => {
  class ApiError extends Error {
    constructor(
      readonly code: string,
      message: string,
    ) {
      super(message)
    }
  }
  return {
    ApiError,
    badRequest: (message: string) => new ApiError('bad_request', message),
    notFound: (what: string) => new ApiError('not_found', `${what} not found`),
  }
})

import { db } from '@/lib/db'

import { prepareTurn } from './chat-service'

let userId = ''

beforeAll(() => {
  execFileSync('npx', ['prisma', 'db', 'push', '--skip-generate'], {
    env: { ...process.env },
    stdio: 'ignore',
  })
}, 60_000)

afterAll(async () => {
  await db.$disconnect()
  rmSync(dir, { recursive: true, force: true })
})

async function newChat(): Promise<string> {
  if (!userId) {
    userId = (await db.user.create({ data: { email: 'turns@example.test' } })).id
  }
  return (await db.chat.create({ data: { userId, model: 'llama3.1' } })).id
}

async function sendAtOnce(chatId: string, n: number) {
  return Promise.allSettled(
    Array.from({ length: n }, (_, i) =>
      prepareTurn(userId, { chatId, intent: 'send', content: `message ${i}` }),
    ),
  )
}

describe('simultaneous sends to one chat', () => {
  it.each([2, 5, 10])('%i at once all succeed with contiguous, paired positions', async (n) => {
    const chatId = await newChat()

    const results = await sendAtOnce(chatId, n)

    expect(results.filter((r) => r.status === 'rejected')).toEqual([])
    const rows = await db.message.findMany({
      where: { chatId },
      orderBy: { position: 'asc' },
      select: { role: true, content: true, position: true },
    })
    expect(rows.map((r) => r.position)).toEqual(Array.from({ length: 2 * n }, (_, i) => i))
    // Each user message is followed by its own empty assistant row.
    for (let i = 0; i < rows.length; i += 2) {
      expect(rows[i]!.role).toBe('user')
      expect(rows[i + 1]!).toMatchObject({ role: 'assistant', content: '' })
    }
    // No user message lost.
    expect(rows.filter((r) => r.role === 'user').map((r) => r.content).sort()).toEqual(
      Array.from({ length: n }, (_, i) => `message ${i}`).sort(),
    )
  }, 60_000)

  it('keeps appending after existing history', async () => {
    const chatId = await newChat()
    await prepareTurn(userId, { chatId, intent: 'send', content: 'first' })

    await sendAtOnce(chatId, 3)

    const positions = (
      await db.message.findMany({ where: { chatId }, orderBy: { position: 'asc' } })
    ).map((m) => m.position)
    expect(positions).toEqual([0, 1, 2, 3, 4, 5, 6, 7])
  }, 60_000)
})

describe('an existing database with duplicate positions', () => {
  it('is renumbered in order so the unique index can be pushed', async () => {
    const chatId = await newChat()
    const other = await newChat()
    // What older versions could write: two turns sharing positions 0 and 1.
    await db.$executeRawUnsafe('DROP INDEX "Message_chatId_position_key"')
    const at = (s: number) => new Date(Date.UTC(2026, 0, 1, 0, 0, s))
    for (const [content, role, position, s] of [
      ['first', 'user', 0, 1],
      ['', 'assistant', 1, 2],
      ['second', 'user', 0, 3],
      ['', 'assistant', 1, 4],
    ] as const) {
      await db.message.create({ data: { chatId, content, role, position, createdAt: at(s) } })
    }
    await db.message.create({ data: { chatId: other, content: 'gap', role: 'user', position: 7 } })

    const env = { ...process.env }
    execFileSync('node', ['prisma/before-push.mjs'], { env, stdio: 'ignore' })
    execFileSync('npx', ['prisma', 'db', 'push', '--skip-generate'], { env, stdio: 'ignore' })

    const rows = await db.message.findMany({
      where: { chatId },
      orderBy: { position: 'asc' },
      select: { content: true, position: true },
    })
    expect(rows).toEqual([
      { content: 'first', position: 0 },
      { content: 'second', position: 1 },
      { content: '', position: 2 },
      { content: '', position: 3 },
    ])
    // Chats without duplicates keep their positions, gaps included.
    expect((await db.message.findFirstOrThrow({ where: { chatId: other } })).position).toBe(7)
  }, 60_000)
})
