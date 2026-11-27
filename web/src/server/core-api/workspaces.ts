import 'server-only'

import { ProviderError } from '@/lib/llm/types'
import { asRole, type Role } from '@/lib/roles'

/**
 * In the lite profile every web user works in one shared team workspace in
 * core-api, as in v1, where documents are shared. The web app owns its users
 * and their roles; before acting for a user it sets their role there with its
 * own service token (core-api's api/internal.py), and remembers that per role.
 */

type CoreRole = 'owner' | 'editor' | 'reader'

const CORE_ROLES: Record<Role, CoreRole> = { admin: 'owner', user: 'editor', viewer: 'reader' }

export function coreRole(webRole: string): CoreRole {
  return CORE_ROLES[asRole(webRole)]
}

interface Options {
  baseUrl: string
  serviceToken: string
  fetch?: typeof globalThis.fetch
}

const remembered = new Map<string, string>()

export async function teamWorkspaceId(
  userId: string,
  webRole: string,
  { baseUrl, serviceToken, fetch = globalThis.fetch }: Options,
): Promise<string> {
  const role = coreRole(webRole)
  const key = `${userId}:${role}`
  const known = remembered.get(key)
  if (known) return known

  let response: Response
  try {
    response = await fetch(
      `${baseUrl.replace(/\/$/, '')}/api/v1/internal/team-members/${encodeURIComponent(userId)}`,
      {
        method: 'PUT',
        headers: { Authorization: `Bearer ${serviceToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role }),
        cache: 'no-store',
      },
    )
  } catch {
    throw new ProviderError()
  }
  if (!response.ok) {
    await response.body?.cancel().catch(() => undefined)
    throw new ProviderError()
  }
  const body = (await response.json().catch(() => null)) as { data?: { workspace_id?: unknown } } | null
  const workspaceId = body?.data?.workspace_id
  if (typeof workspaceId !== 'string') {
    throw new ProviderError()
  }
  remembered.set(key, workspaceId)
  return workspaceId
}

/** For tests. */
export function resetWorkspaceCache(): void {
  remembered.clear()
}
