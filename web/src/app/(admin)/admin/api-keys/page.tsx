import type { Metadata } from 'next'

import { AdminApiKeysPanel } from '@/components/admin/api-keys-panel'
import { PageHeader } from '@/components/admin/page-header'

export const metadata: Metadata = { title: 'API keys' }

export default function AdminApiKeysPage() {
  return (
    <>
      <PageHeader
        title="API keys"
        description="Every personal API key on this instance. A key acts as its owner, with their role. Revoke one that is lost or no longer used; it stops working within a minute."
      />
      <AdminApiKeysPanel />
    </>
  )
}
