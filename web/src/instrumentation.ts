/**
 * Runs once when the server starts. While the instance has no admin, prints a
 * fresh setup code for the first sign-up to present.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== 'nodejs') return
  const { bootstrapAdmin } = await import('@/server/identity/admin')
  try {
    const code = await bootstrapAdmin()
    if (code) {
      console.log(
        [
          '',
          `First admin setup code: ${code}`,
          'Sign up with it in the "Setup code" field to become the admin.',
          'The code is replaced on each restart until an admin exists.',
          '',
        ].join('\n'),
      )
    }
  } catch (error) {
    // The schema may not exist yet in a fresh dev checkout; the first sign-up
    // creates the same state, so nothing is lost.
    console.warn('Setup code not issued at startup:', error)
  }
  const { ensureAuditTriggers } = await import('@/server/audit')
  try {
    await ensureAuditTriggers()
  } catch (error) {
    // Same as above: a fresh checkout may not have the table yet.
    console.warn('audit triggers at startup failed:', error)
  }
}
