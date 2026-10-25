import type { Metadata } from 'next'

import { PageHeader } from '@/components/admin/page-header'
import { UsersPanel } from '@/components/admin/users-panel'
import { auth } from '@/lib/auth'

export const metadata: Metadata = { title: 'Users' }

export default async function AdminUsersPage() {
  // The layout has already checked the admin role.
  const session = await auth()

  return (
    <>
      <PageHeader
        title="Users"
        description="A role decides what someone can do in the chat and with their API keys. viewer: chat · user: chat and add documents · admin: everything, including this console. Changes apply to API keys at once and to open sessions within five minutes."
      />
      <UsersPanel currentUserId={session?.user?.id ?? ''} />
    </>
  )
}
