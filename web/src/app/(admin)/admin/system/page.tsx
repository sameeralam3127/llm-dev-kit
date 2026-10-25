import type { Metadata } from 'next'

import { ConfigPanel, ModelsPanel } from '@/components/admin/config-panel'
import { HealthPanel } from '@/components/admin/health-panel'
import { PageHeader } from '@/components/admin/page-header'
import { adminPageUser } from '@/server/admin-page'
import { getConfig } from '@/server/services/admin-service'

export const metadata: Metadata = { title: 'Health & settings' }

export default async function AdminSystemPage() {
  // This page renders configuration on the server, so it checks the role
  // itself rather than relying on the layout, which renders in parallel.
  if (!(await adminPageUser())) return null

  return (
    <>
      <PageHeader
        title="Health & settings"
        description="Whether each service is up, and how this instance is configured."
      />
      <div className="space-y-6">
        <HealthPanel />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ConfigPanel config={getConfig()} />
          </div>
          <ModelsPanel />
        </div>
      </div>
    </>
  )
}
