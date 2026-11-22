// @vitest-environment node
import { describe, expect, it } from 'vitest'

import { sqliteDatasourceUrl } from './db'

describe('sqliteDatasourceUrl', () => {
  it('uses one connection for SQLite', () => {
    expect(sqliteDatasourceUrl('file:/data/web.db')).toBe('file:/data/web.db?connection_limit=1')
    expect(sqliteDatasourceUrl('file:./dev.db?socket_timeout=10')).toBe(
      'file:./dev.db?socket_timeout=10&connection_limit=1',
    )
  })

  it('leaves an explicit limit and other databases alone', () => {
    expect(sqliteDatasourceUrl('file:x.db?connection_limit=4')).toBe('file:x.db?connection_limit=4')
    expect(sqliteDatasourceUrl('postgresql://h/db')).toBe('postgresql://h/db')
    expect(sqliteDatasourceUrl(undefined)).toBeUndefined()
  })
})
