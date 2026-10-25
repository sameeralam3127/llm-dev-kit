import { describe, expect, it } from 'vitest'

import { deriveTitle, plural } from '@/lib/utils'

describe('deriveTitle', () => {
  it('drops empty code fences left by a prompt template', () => {
    const prompt =
      'I am seeing this error and cannot work out why:\n\n```\n\n```\n\nWhat are the likely causes?'
    expect(deriveTitle(prompt, 80)).toBe(
      'I am seeing this error and cannot work out why: What are the likely causes?',
    )
  })

  it('keeps the code but not the fences, language tags or backticks', () => {
    expect(deriveTitle('Why does ```python\nprint(x)\n``` fail with `NameError`?')).toBe(
      'Why does print(x) fail with NameError?',
    )
  })

  it('drops heading, quote and list markers', () => {
    expect(deriveTitle('## Plan\n- step one\n> quoted\n1. first')).toBe(
      'Plan step one quoted first',
    )
  })

  it('cuts long text at a word boundary', () => {
    expect(deriveTitle('word '.repeat(30), 20)).toBe('word word word word…')
  })

  it('falls back when nothing readable is left', () => {
    expect(deriveTitle('```\n```')).toBe('New chat')
  })
})

describe('plural', () => {
  it('uses the singular for exactly one', () => {
    expect(plural(1, 'chunk')).toBe('1 chunk')
    expect(plural(0, 'chunk')).toBe('0 chunks')
    expect(plural(3, 'entry', 'entries')).toBe('3 entries')
  })
})
