import type { Metadata } from 'next'

import { OverviewPanel } from '@/components/admin/overview-panel'
import { PageHeader } from '@/components/admin/page-header'

export const metadata: Metadata = { title: 'Overview' }

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
