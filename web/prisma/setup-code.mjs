export const SETUP_ID = 'instance'
export const SETUP_CODE_MINUTES = 15

/**
 * @param {string} code
 * @param {string} email
 */
export async function hashSetupCode(code, email) {
  const input = new TextEncoder().encode(`${email.trim().toLowerCase()}\0${code}`)
  const digest = await crypto.subtle.digest('SHA-256', input)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}
