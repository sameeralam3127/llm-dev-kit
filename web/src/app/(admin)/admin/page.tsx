import type { Metadata } from 'next'

import { OverviewPanel } from '@/components/admin/overview-panel'
import { PageHeader } from '@/components/admin/page-header'

// The layout's title template applies to child segments only, not this page.
export const metadata: Metadata = { title: 'Overview · Admin' }

export default function AdminOverviewPage() {
  return (
    <>
      <PageHeader
        title="Overview"
        description="How this instance is being used, and whether its services are up."
      />
      <OverviewPanel />
    </>
  )
}
