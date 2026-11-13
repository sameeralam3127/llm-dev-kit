import type { Metadata } from 'next'

import { AuditPanel } from '@/components/admin/audit-panel'
import { PageHeader } from '@/components/admin/page-header'

export const metadata: Metadata = { title: 'Audit log' }

export default function AdminAuditPage() {
  return (
    <>
      <PageHeader
        title="Audit log"
        description="Who changed what in this console: role changes, API key revocations, document uploads and clears. Entries are append-only; the database refuses to edit or delete them. It never holds keys, passwords or document text."
      />
      <AuditPanel />
    </>
  )
}
