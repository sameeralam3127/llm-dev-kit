import 'server-only'

import { redirect } from 'next/navigation'

import { auth } from '@/lib/auth'
import { ROUTES } from '@/lib/constants'
import { roleOf } from '@/server/http'
import type { ShellUser } from '@/types/user'

/**
 * The signed-in admin, or `null` for anyone else; no session goes to sign-in.
 * The role comes from the database, so a demotion applies on the next load.
 */
export async function adminPageUser(): Promise<(ShellUser & { id: string }) | null> {
  const session = await auth()
  if (!session?.user?.id) redirect(ROUTES.login)
  if ((await roleOf(session.user.id)) !== 'admin') return null
  return {
    id: session.user.id,
    name: session.user.name ?? null,
    email: session.user.email ?? null,
    image: session.user.image ?? null,
    isAdmin: true,
  }
}
