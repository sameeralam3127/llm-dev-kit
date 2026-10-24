import type { Metadata } from 'next'
import Link from 'next/link'

import { AdminShell } from '@/components/admin/admin-shell'
import { Button } from '@/components/ui/button'
import { ROUTES } from '@/lib/constants'
import { adminPageUser } from '@/server/admin-page'

export const metadata: Metadata = { title: { default: 'Admin', template: '%s · Admin · LLM Dev Kit' } }
export const dynamic = 'force-dynamic'

/**
 * The admin console has its own frame, not the chat's. Every panel loads its
 * data from /api/admin, which answers non-admins with 403; non-admins get an
 * explanation here instead of the console.
 */
export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const user = await adminPageUser()

  if (!user) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="font-mono text-sm text-muted-foreground">403</p>
        <h1 className="text-lg font-semibold">You do not have access to this page</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          It needs the admin role. Ask an admin of this instance if you need it.
        </p>
        <Button asChild>
          <Link href={ROUTES.home}>Back to chats</Link>
        </Button>
      </div>
    )
  }

  return <AdminShell user={user}>{children}</AdminShell>
}
