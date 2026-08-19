import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Derive a chat title from its first user message. */
export function deriveTitle(text: string, maxLength = 60): string {
  const normalised = text.replace(/\s+/g, ' ').trim()
  if (!normalised) return 'New chat'
  if (normalised.length <= maxLength) return normalised

  const cut = normalised.slice(0, maxLength)
  const lastSpace = cut.lastIndexOf(' ')
  return `${(lastSpace > maxLength * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`
}

export function initialsOf(nameOrEmail: string | null | undefined): string {
  if (!nameOrEmail) return '?'
  const source = nameOrEmail.includes('@')
    ? (nameOrEmail.split('@')[0] ?? nameOrEmail)
    : nameOrEmail

  const parts = source.split(/[\s._-]+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return (parts[0] ?? '?').slice(0, 2).toUpperCase()
  return `${parts[0]?.[0] ?? ''}${parts[1]?.[0] ?? ''}`.toUpperCase()
}

/**
 * Copy text using the async clipboard API, falling back to a hidden textarea
 * for insecure origins (plain-http LAN deployments) where it is unavailable.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }

    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

/** Stable, dependency-free id for optimistic client-side records. */
export function tempId(prefix = 'tmp'): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36)}`
}

export function isAbortError(error: unknown): boolean {
  return (
    error instanceof DOMException && error.name === 'AbortError'
  ) || (error instanceof Error && error.name === 'AbortError')
}
