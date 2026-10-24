import type { Metadata } from 'next'

import { DocumentsPanel } from '@/components/admin/documents-panel'
import { PageHeader } from '@/components/admin/page-header'

export const metadata: Metadata = { title: 'Documents' }

export default function AdminDocumentsPage() {
  return (
    <>
      <PageHeader
        title="Documents"
        description="The PDFs answers are grounded in. When documents are indexed, answers come only from them."
      />
      <DocumentsPanel />
    </>
  )
}
