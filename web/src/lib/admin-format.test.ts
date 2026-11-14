import { describe, expect, it } from 'vitest'

import { describeAudit, formatBytes, formatDuration } from '@/lib/admin-format'

describe('formatBytes', () => {
  it('reads like a file manager', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(812)).toBe('812 B')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(10 * 1024)).toBe('10 KB')
    expect(formatBytes(64 * 1024 * 1024)).toBe('64 MB')
  })
})

describe('formatDuration', () => {
  it('uses the largest sensible unit', () => {
    expect(formatDuration(850)).toBe('850 ms')
    expect(formatDuration(12_400)).toBe('12 s')
    expect(formatDuration(125_000)).toBe('2 min 5 s')
    expect(formatDuration(120_000)).toBe('2 min')
    expect(formatDuration(-5)).toBe('0 ms')
  })
})

describe('describeAudit', () => {
  it('says what changed for each kind of entry', () => {
    expect(
      describeAudit({
        action: 'user.role_changed',
        detail: { email: 'sam@example.test', from: 'user', to: 'admin' },
      }),
    ).toBe('sam@example.test: user → admin')
    expect(
      describeAudit({
        action: 'api_key.revoked',
        detail: { name: 'CI', prefix: 'sk-ldk-Ab', owner: 'sam@example.test' },
      }),
    ).toBe('CI (sk-ldk-Ab…), owned by sam@example.test')
    expect(
      describeAudit({ action: 'document.uploaded', detail: { bytes: 2048, chunks: 7 } }),
    ).toBe('7 chunks, 2 KB')
    expect(describeAudit({ action: 'cache.cleared', detail: { cleared: 3 } })).toBe('3 cached answers')
  })

  it('uses the singular for exactly one', () => {
    expect(describeAudit({ action: 'document.uploaded', detail: { bytes: 604, chunks: 1 } })).toBe('1 chunk, 604 B')
    expect(describeAudit({ action: 'cache.cleared', detail: { cleared: 1 } })).toBe('1 cached answer')
    expect(describeAudit({ action: 'document.index_cleared', detail: { cacheCleared: 1 } })).toBe(
      '1 cached answer dropped too',
    )
  })

  it('copes with missing details and unknown actions', () => {
    expect(describeAudit({ action: 'user.role_changed', detail: null })).toBe('')
    expect(describeAudit({ action: 'something.new', detail: { a: 1, b: 'x' } })).toBe('a: 1, b: x')
    expect(describeAudit({ action: 'something.new', detail: null })).toBe('')
    expect(
      describeAudit({ action: 'document.index_cleared', detail: { cacheCleared: null } }),
    ).toBe('Cached answers could not be cleared')
  })
})
