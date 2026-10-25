'use client'

import {
  Activity,
  ArrowLeft,
  FileText,
  KeyRound,
  LayoutDashboard,
  type LucideIcon,
  Users,
} from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { BrandMark } from '@/components/brand/brand-mark'
import { UserMenu } from '@/components/sidebar/user-menu'
import { ROUTES } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { ShellUser } from '@/types/user'

interface NavItem {
  href: string
  label: string
  icon: LucideIcon
}

const OVERVIEW: NavItem = { href: ROUTES.admin, label: 'Overview', icon: LayoutDashboard }

export const ADMIN_SECTIONS: { label: string; items: NavItem[] }[] = [
  { label: 'Overview', items: [OVERVIEW] },
  {
    label: 'Manage',
    items: [
      { href: ROUTES.adminUsers, label: 'Users', icon: Users },
      { href: ROUTES.adminApiKeys, label: 'API keys', icon: KeyRound },
      { href: ROUTES.adminDocuments, label: 'Documents', icon: FileText },
    ],
  },
  {
    label: 'System',
    items: [{ href: ROUTES.adminSystem, label: 'Health & settings', icon: Activity }],
  },
]

const ITEMS = ADMIN_SECTIONS.flatMap((section) => section.items)

/** The item for `pathname`: an exact match for Overview, a prefix for the rest. */
export function currentAdminItem(pathname: string): NavItem {
  return (
    ITEMS.find((item) =>
      item.href === ROUTES.admin ? pathname === item.href : pathname.startsWith(item.href),
    ) ?? OVERVIEW
  )
}

interface AdminNavProps {
  user: ShellUser
  /** Closes the mobile drawer after a link is followed. */
  onNavigate?: () => void
}

export function AdminNav({ user, onNavigate }: AdminNavProps) {
  const current = currentAdminItem(usePathname())

  return (
    <div className="flex h-full flex-col text-sidebar-foreground">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-sidebar-border px-4">
        <BrandMark size="sm" />
        <div className="min-w-0 leading-tight">
          <p className="truncate text-[0.9375rem] font-semibold tracking-tight">LLM Dev Kit</p>
          <p className="text-xs text-muted-foreground">Admin console</p>
        </div>
      </div>

      <nav aria-label="Admin" className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {ADMIN_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="px-2 pb-1.5 text-[0.6875rem] font-medium uppercase tracking-wider text-muted-foreground">
              {section.label}
            </p>
            <ul className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = current.href === href
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      onClick={onNavigate}
                      aria-current={active ? 'page' : undefined}
                      className={cn(
                        'flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors',
                        active
                          ? 'bg-sidebar-accent font-medium text-foreground'
                          : 'text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground',
                      )}
                    >
                      <Icon className={cn('size-4 shrink-0', active && 'text-primary')} />
                      {label}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="space-y-2 border-t border-sidebar-border p-3">
        <Link
          href={ROUTES.home}
          onClick={onNavigate}
          className="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to chat
        </Link>
        <UserMenu user={user} />
      </div>
    </div>
  )
}
