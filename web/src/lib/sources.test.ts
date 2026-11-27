import { describe, expect, it } from 'vitest'

import { parseSources, parseStoredSources } from './sources'

describe('parseSources', () => {
  it('keeps the fields core-api sends and drops the rest', () => {
    expect(
      parseSources([
        { index: 1, chunk_id: 'c1', title: 'Handbook.pdf', page: 4, snippet: '  Leave is 25 days. ' },
      ]),
    ).toEqual([{ index: 1, title: 'Handbook.pdf', page: 4, snippet: 'Leave is 25 days.' }])
  })

  it('numbers untitled passages by position, as rag-service sends them', () => {
    expect(parseSources([{ snippet: 'a' }, { snippet: 'b', title: null, page: null }])).toEqual([
      { index: 1, title: null, page: null, snippet: 'a' },
      { index: 2, title: null, page: null, snippet: 'b' },
    ])
  })

  it('skips malformed entries instead of failing the answer', () => {
    expect(parseSources([null, 'x', { title: 'no snippet' }, { snippet: 'ok', page: -2 }])).toEqual([
      { index: 4, title: null, page: null, snippet: 'ok' },
    ])
    expect(parseSources({ not: 'an array' })).toEqual([])
  })

  it('caps snippet length and count', () => {
    const many = Array.from({ length: 30 }, () => ({ snippet: 'x'.repeat(2000) }))
    const parsed = parseSources(many)
    expect(parsed).toHaveLength(20)
    expect(parsed[0]?.snippet).toHaveLength(600)
  })
})

describe('parseStoredSources', () => {
  it('reads the column, and treats empty or corrupt values as no sources', () => {
    expect(parseStoredSources(JSON.stringify([{ snippet: 'a' }]))).toHaveLength(1)
    expect(parseStoredSources(null)).toEqual([])
    expect(parseStoredSources('{oops')).toEqual([])
  })
})
