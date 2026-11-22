/**
 * The Content-Security-Policy every page is served with (set per request in
 * middleware.ts, so each response has its own script nonce).
 *
 * - Scripts run only with this response's nonce; 'strict-dynamic' lets those
 *   scripts load the app's chunks. An injected inline script has no nonce.
 * - Images come only from this app and GitHub avatars, so a model answer
 *   cannot make the browser fetch an attacker's URL with data in it.
 * - Inline styles stay allowed: React's style attributes need them, and a
 *   nonce would disable 'unsafe-inline' for style attributes too.
 */
const GITHUB_AVATARS = 'https://avatars.githubusercontent.com'

export function contentSecurityPolicy(nonce: string, { dev = false } = {}): string {
  const directives: Record<string, string[]> = {
    'default-src': ["'self'"],
    // The dev server evaluates code for fast refresh and talks over a websocket.
    'script-src': [`'nonce-${nonce}'`, "'strict-dynamic'", ...(dev ? ["'unsafe-eval'"] : [])],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", 'data:', 'blob:', GITHUB_AVATARS],
    'font-src': ["'self'", 'data:'],
    'connect-src': ["'self'", ...(dev ? ['ws:'] : [])],
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    'frame-ancestors': ["'none'"],
  }
  return Object.entries(directives)
    .map(([name, values]) => `${name} ${values.join(' ')}`)
    .join('; ')
}

/** 128 random bits, base64. Works in the edge and Node runtimes alike. */
export function newNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return btoa(String.fromCharCode(...bytes))
}
