import { ROUTES } from '@/lib/constants'

/**
 * Validate a `callbackUrl` query parameter and return a safe in-app path.
 *
 * Only same-origin relative paths are accepted, so a crafted
 * `?callbackUrl=https://evil.example` (or a backslash / tab / newline trick
 * that browsers normalise into a cross-origin URL) cannot turn sign-in into an
 * open redirect. Anything that does not resolve to a same-origin path falls
 * back to `ROUTES.home`.
 */
const BASE = 'http://app.invalid'

export function safeCallback(raw: string | undefined): string {
  if (!raw) return ROUTES.home
  let url: URL
  try {
    url = new URL(raw, BASE)
  } catch {
    return ROUTES.home
  }
  if (url.origin !== BASE) return ROUTES.home
  if (url.pathname.startsWith('//')) return ROUTES.home
  return url.pathname + url.search + url.hash
}