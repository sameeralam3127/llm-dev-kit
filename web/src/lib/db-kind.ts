/**
 * The web app runs on SQLite by default and on Postgres in the v3 lite profile
 * (the image is built with DATABASE_PROVIDER=postgresql). The few places where
 * the two differ ask here.
 */
export function isPostgres(url: string | undefined = process.env.DATABASE_URL): boolean {
  return Boolean(url && /^postgres(ql)?:\/\//.test(url))
}

/**
 * A case-insensitive "contains" filter. SQLite's LIKE already ignores ASCII
 * case; Postgres needs `mode`. The cast is because the client's types come
 * from whichever provider the image was built for, and SQLite's have no mode.
 */
export function containsText(
  q: string,
  url: string | undefined = process.env.DATABASE_URL,
): { contains: string } {
  return isPostgres(url)
    ? ({ contains: q, mode: 'insensitive' } as { contains: string })
    : { contains: q }
}
