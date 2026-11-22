// @vitest-environment node
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { containsText, isPostgres } from './db-kind'

describe('which database the app runs on', () => {
  it('is Postgres only for a postgres URL', () => {
    expect(isPostgres('postgresql://u@db:5432/ldk?schema=app')).toBe(true)
    expect(isPostgres('postgres://u@db/ldk')).toBe(true)
    expect(isPostgres('file:/data/web.db')).toBe(false)
    expect(isPostgres(undefined)).toBe(false)
  })
})

describe('chat search', () => {
  it('ignores case on both databases', () => {
    // SQLite's LIKE already ignores ASCII case; Postgres needs to be told.
    expect(containsText('Budget', 'file:/data/web.db')).toEqual({ contains: 'Budget' })
    expect(containsText('Budget', 'postgresql://db/ldk')).toEqual({ contains: 'Budget', mode: 'insensitive' })
  })
})

describe('prisma/use-provider.mjs', () => {
  const schema = readFileSync(join(__dirname, '../../prisma/schema.prisma'), 'utf8')
  const run = (provider: string) => {
    const dir = mkdtempSync(join(tmpdir(), 'ldk-schema-'))
    const path = join(dir, 'schema.prisma')
    writeFileSync(path, schema)
    execFileSync('node', [join(__dirname, '../../prisma/use-provider.mjs'), provider, path])
    return readFileSync(path, 'utf8')
  }

  it('switches only the datasource provider', () => {
    const postgres = run('postgresql')
    expect(postgres).toMatch(/datasource db \{\s*provider = "postgresql"/)
    expect(postgres.replace('"postgresql"', '"sqlite"')).toBe(schema)
  })

  it('leaves the SQLite schema untouched', () => {
    expect(run('sqlite')).toBe(schema)
  })

  it('refuses a provider it does not know', () => {
    expect(() => run('mongodb')).toThrow()
  })
})
