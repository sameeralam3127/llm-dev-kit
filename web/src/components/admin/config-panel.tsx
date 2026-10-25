'use client'

import type * as React from 'react'

import { Panel } from '@/components/admin/page-header'
import { StatusLabel } from '@/components/admin/status'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useModels } from '@/hooks/use-models'
import { isOllamaCloud } from '@/lib/models'
import { plural } from '@/lib/utils'
import type { AdminConfig } from '@/types/admin'
import type { ModelInfo } from '@/types/chat'

function Row({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="grid gap-1 px-4 py-3 sm:grid-cols-[14rem_1fr] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm">
        {children}
        {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      </dd>
    </div>
  )
}

function OnOff({ on }: { on: boolean }) {
  return <StatusLabel status={on ? 'ok' : 'off'} label={on ? 'On' : 'Off'} className="text-sm text-foreground" />
}

/** What this instance is set up to do. Settings live in `.env`; this page only reads them. */
export function ConfigPanel({ config }: { config: AdminConfig }) {
  return (
    <Panel
      title="Configuration"
      description="Read from the environment. Change these in .env, then run docker compose up -d."
    >
      <dl className="divide-y">
        <Row label="Public address" hint="WEB_PUBLIC_URL: what people type into their browser.">
          <span className="font-mono text-xs">{config.publicUrl ?? 'Not set (uses the request host)'}</span>
        </Row>
        <Row label="Open registration" hint="ALLOW_REGISTRATION: anyone who can reach the app can sign up while this is on.">
          <OnOff on={config.registrationOpen} />
        </Row>
        <Row label="Sign-in methods">
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="secondary" className="font-normal">Password</Badge>
            <Badge variant={config.signIn.github ? 'secondary' : 'outline'} className="font-normal">
              GitHub {config.signIn.github ? '' : '(off)'}
            </Badge>
            <Badge variant={config.signIn.sso ? 'secondary' : 'outline'} className="font-normal">
              Single sign-on {config.signIn.sso ? '' : '(off)'}
            </Badge>
          </div>
        </Row>
        <Row label="Default model" hint="DEFAULT_MODEL: used when a chat has not picked one.">
          <span className="font-mono text-xs">{config.defaultModel}</span>
        </Row>
        <Row label="Token issuer and audience" hint="Must match the Python services.">
          <span className="font-mono text-xs">
            {config.identity.issuer} → {config.identity.audience}
          </span>
        </Row>
        <Row label="Services">
          <span className="block font-mono text-xs">RAG {config.services.rag}</span>
          <span className="block font-mono text-xs">Models {config.services.llm}</span>
        </Row>
      </dl>
    </Panel>
  )
}

const MODEL_GROUPS = [
  {
    id: 'local',
    title: 'On this machine',
    note: 'Run by Ollama on the host. Nothing leaves the machine.',
  },
  {
    id: 'ollama-cloud',
    title: 'Ollama cloud',
    note: 'Listed by the local Ollama but run on ollama.com: questions and document text leave the machine.',
  },
  {
    id: 'provider',
    title: 'Cloud providers',
    note: 'Always listed; they answer only with a key in .env or in the request.',
  },
] as const

type ModelGroup = (typeof MODEL_GROUPS)[number]['id']

function groupOf(model: ModelInfo): ModelGroup {
  if (model.provider !== 'local') return 'provider'
  return isOllamaCloud(model.id) ? 'ollama-cloud' : 'local'
}

/** Models the chat can offer right now, grouped by where they run. */
export function ModelsPanel() {
  const models = useModels()
  const all = models.data ?? []

  return (
    <Panel title="Models" description={models.data ? plural(all.length, 'model') : 'From the model service'}>
      {models.isLoading ? (
        <div className="space-y-2 p-4">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      ) : models.isError ? (
        <p role="alert" className="px-4 py-3 text-sm text-destructive">
          Could not list models: {models.error.message}
        </p>
      ) : all.length === 0 ? (
        <p className="px-4 py-3 text-sm text-muted-foreground">
          No models yet. Pull one on the host, for example ollama pull llama3.1.
        </p>
      ) : (
        <div className="scrollbar-thin max-h-[32rem] divide-y overflow-y-auto">
          {MODEL_GROUPS.map((group) => {
            const inGroup = all.filter((model) => groupOf(model) === group.id)
            if (inGroup.length === 0) return null
            return (
              <div key={group.id}>
                <div className="bg-muted/40 px-4 py-2">
                  <p className="flex items-center justify-between text-xs font-medium">
                    {group.title}
                    <span className="tabular-nums text-muted-foreground">{inGroup.length}</span>
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{group.note}</p>
                </div>
                <ul className="divide-y">
                  {inGroup.map((model) => (
                    <li key={model.id} className="flex items-center justify-between gap-3 px-4 py-2">
                      <span className="truncate font-mono text-xs">{model.id}</span>
                      {group.id === 'provider' ? (
                        <Badge variant="outline" className="shrink-0 font-normal">
                          {model.provider}
                        </Badge>
                      ) : group.id === 'ollama-cloud' ? (
                        <Badge variant="destructive" className="shrink-0 font-normal">
                          leaves the machine
                        </Badge>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      )}
    </Panel>
  )
}
