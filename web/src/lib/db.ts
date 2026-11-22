import { PrismaClient } from '@prisma/client'

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined
}

/**
 * SQLite takes one writer at a time. With several pooled connections, a
 * second writer waits for the lock inside SQLite (busy_timeout, 5 s) while
 * occupying one of the query engine's worker threads, of which there is one
 * per CPU. Once the waiters fill those threads, the transaction holding the
 * lock cannot run its next statement, and every transaction expires. One
 * connection makes Prisma queue the work instead, which SQLite needs anyway.
 */
export function sqliteDatasourceUrl(url: string | undefined): string | undefined {
  if (!url?.startsWith('file:') || /[?&]connection_limit=/.test(url)) return url
  return `${url}${url.includes('?') ? '&' : '?'}connection_limit=1`
}

/**
 * A single client per process. Next.js dev server hot-reloads modules, which
 * would otherwise leak a new connection pool on every save.
 */
export const db =
  globalForPrisma.prisma ??
  new PrismaClient({
    datasourceUrl: sqliteDatasourceUrl(process.env.DATABASE_URL),
    log:
      process.env.NODE_ENV === 'development'
        ? ['warn', 'error']
        : ['error'],
  })

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = db
}
