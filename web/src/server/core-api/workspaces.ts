import 'server-only'

import { createHash } from 'node:crypto'

import { ProviderError } from '@/lib/llm/types'

/**
 * Every web user works in a personal workspace in core-api, found or created
 * on first use with the user's own session token. core-api keeps no user
 * table: memberships hold the web app's user id, so the workspace is all
 * there is to provision.
 */

interface WorkspaceRow {
  id: string
  slug: string
}

interface Options {
  baseUrl: string
  fetch?: typeof globalThis.fetch
}

const remembered = new Map<string, string>()

/** Deterministic and within core-api's slug rule, whatever the user id holds. */
export function personalSlug(userId: string): string {
  return `user-${createHash('sha256').update(userId).digest('hex').slice(0, 32)}`
}

export async function personalWorkspaceId(
  userId: string,
  token: string,
  { baseUrl, fetch = globalThis.fetch }: Options,
): Promise<string> {
  const known = remembered.get(userId)
  if (known) return known

  const slug = personalSlug(userId)
  const url = `${baseUrl.replace(/\/$/, '')}/api/v1/workspaces`
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }

  // core-api wraps every response as {"data": ...}.
  const find = async (): Promise<string | undefined> => {
    const response = await call(fetch, url, { headers })
    const { data } = (await response.json()) as { data?: WorkspaceRow[] }
    if (!Array.isArray(data)) throw unexpected()
    return data.find((workspace) => workspace.slug === slug)?.id
  }

  let id = await find()
  if (!id) {
    const response = await call(
      fetch,
      url,
      { method: 'POST', headers, body: JSON.stringify({ slug, name: 'Personal' }) },
      [409],
    )
    // 409: another request for the same user created it first.
    id =
      response.status === 409
        ? await find()
        : ((await response.json()) as { data?: WorkspaceRow }).data?.id
  }
  if (!id) throw new ProviderError('Could not set up your workspace', 'upstream_error')

  remembered.set(userId, id)
  return id
}

async function call(
  fetch: typeof globalThis.fetch,
  url: string,
  init: RequestInit,
  allowed: number[] = [],
): Promise<Response> {
  let response: Response
  try {
    response = await fetch(url, { ...init, cache: 'no-store' })
  } catch {
    throw new ProviderError('The document service is unreachable', 'upstream_error')
  }
  if (!response.ok && !allowed.includes(response.status)) {
    throw new ProviderError(
      `The document service answered ${response.status}`,
      'upstream_error',
    )
  }
  return response
}

function unexpected(): ProviderError {
  return new ProviderError('The document service gave an unexpected answer', 'upstream_error')
}

/** For tests. */
export function resetWorkspaceCache(): void {
  remembered.clear()
}
