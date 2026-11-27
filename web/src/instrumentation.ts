export async function register() {
  if (process.env.NEXT_RUNTIME !== 'nodejs') return
  const { ensureRolesStarted } = await import('@/server/identity/admin')
  const { db } = await import('@/lib/db')
  try {
    await db.$transaction(ensureRolesStarted)
  } catch {
    // The schema may not exist yet in a fresh dev checkout; the first sign-up
    // creates the same state, so nothing is lost.
    console.warn('Could not initialize account roles at startup.')
  }
  const { ensureAuditTriggers } = await import('@/server/audit')
  try {
    await ensureAuditTriggers()
  } catch {
    // Same as above: a fresh checkout may not have the table yet.
    console.warn('Could not initialize audit triggers at startup.')
  }
}
