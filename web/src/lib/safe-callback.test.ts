import { describe, expect, it } from 'vitest'

import { safeCallback } from '@/lib/safe-callback'

describe('safeCallback', () => {
  it('returns home for undefined or empty input', () => {
    expect(safeCallback(undefined)).toBe('/')
    expect(safeCallback('')).toBe('/')
  })

  it('leaves a safe relative path unchanged', () => {
    expect(safeCallback('/c/abc?x=1#m')).toBe('/c/abc?x=1#m')
  })

  it('maps cross-origin URLs to home', () => {
    expect(safeCallback('https://host')).toBe('/')
  })

  it('maps protocol-relative paths to home', () => {
    expect(safeCallback('//host')).toBe('/')
  })

  it('maps backslash tricks to home', () => {
    expect(safeCallback('/\\host')).toBe('/')
  })

  it('maps tab/newline tricks to home', () => {
    expect(safeCallback('/\t/host')).toBe('/')
    expect(safeCallback('/\n/host')).toBe('/')
  })

  it('maps /.//host to home', () => {
    expect(safeCallback('/.//host')).toBe('/')
  })

  it('maps javascript: URLs to home', () => {
    expect(safeCallback('javascript:alert(1)')).toBe('/')
  })
})