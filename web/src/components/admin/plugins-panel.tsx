'use client'

import { Panel } from '@/components/admin/page-header'
import { StatusLabel } from '@/components/admin/status'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { usePluginInventory } from '@/hooks/use-admin'

/**
 * What is installed in each Python service. Read-only on purpose: there are
 * several replicas and a toggle would reach one of them and vanish on restart,
 * and some plugins (authentication) must never be switchable from a web page.
 */
export function PluginsPanel() {
  const inventory = usePluginInventory()
  const data = inventory.data

  return (
    <Panel
      title="Plugins"
      description="Installed in each service, read from its plugin registry. Permissions are what a plugin declares it does: disclosure, not a sandbox. Configuration and secrets are never shown."
    >
      {inventory.isLoading ? (
        <div className="space-y-2 p-4">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
        </div>
      ) : inventory.isError ? (
        <p role="alert" className="px-4 py-3 text-sm text-destructive">
          Could not load plugins: {inventory.error.message}
        </p>
      ) : (
        <>
          {data && data.unreachable.length > 0 && (
            <p role="alert" className="border-b px-4 py-2.5 text-sm text-destructive">
              Could not reach {data.unreachable.join(' and ')}, so its plugins are missing from this list.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Installed plugins</caption>
              <thead className="border-b text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-medium">Plugin</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Service</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">State</th>
                  <th scope="col" className="px-4 py-2.5 font-medium">Declares</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data?.plugins.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                      No plugins reported.
                    </td>
                  </tr>
                )}
                {data?.plugins.map((plugin) => (
                  <tr key={`${plugin.service}:${plugin.kind}:${plugin.name}`}>
                    <th scope="row" className="px-4 py-2.5 font-medium">
                      <span className="font-mono text-xs">
                        {plugin.kind}.{plugin.name}
                      </span>{' '}
                      <span className="text-xs font-normal text-muted-foreground">v{plugin.version}</span>
                      <span className="mt-0.5 block max-w-md text-xs font-normal text-muted-foreground">
                        {plugin.description}
                      </span>
                    </th>
                    <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">{plugin.service}</td>
                    <td className="px-4 py-2.5">
                      <StatusLabel
                        status={plugin.enabled ? 'ok' : 'off'}
                        label={plugin.enabled ? 'Enabled' : 'Disabled'}
                        className="text-sm text-foreground"
                      />
                    </td>
                    <td className="px-4 py-2.5">
                      {plugin.permissions.length ? (
                        <div className="flex flex-wrap gap-1">
                          {plugin.permissions.map((permission) => (
                            <Badge key={permission} variant="outline" className="font-normal">
                              {permission}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground">Nothing</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  )
}
