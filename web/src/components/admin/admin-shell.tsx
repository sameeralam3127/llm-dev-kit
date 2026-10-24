'use client'

import { ChevronRight, Menu, MessageSquare } from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import * as React from 'react'

import { AdminNav, currentAdminItem } from '@/components/admin/admin-nav'
import { ApiKeysDialog } from '@/components/settings/api-keys-dialog'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { ROUTES } from '@/lib/constants'
import { useUiStore } from '@/stores/ui-store'
import type { ShellUser } from '@/types/user'

/**
 * The admin console's frame: its own navigation instead of the chat list,
 * docked from `lg` up and a drawer below it. The account menu's "API keys"
 * entry opens the same dialog as in the chat, so it is mounted here too.
 */
export function AdminShell({ user, children }: { user: ShellUser; children: React.ReactNode }) {
  const pathname = usePathname()
  const current = currentAdminItem(pathname)
  const [navOpen, setNavOpen] = React.useState(false)
  const apiKeysOpen = useUiStore((state) => state.apiKeysOpen)
  const setApiKeysOpen = useUiStore((state) => state.setApiKeysOpen)

  return (
    <div className="relative isolate flex h-dvh w-full overflow-hidden bg-background">
      <a
        href="#admin-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        Skip to content
      </a>

      <aside aria-label="Admin navigation" className="hidden w-64 shrink-0 border-r bg-sidebar lg:block">
        <AdminNav user={user} />
      </aside>

      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" className="w-72 border-r bg-sidebar p-0 lg:hidden">
          <SheetTitle className="sr-only">Admin navigation</SheetTitle>
          <AdminNav user={user} onNavigate={() => setNavOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background px-3 sm:px-6">
          <Button
            variant="ghost"
            size="icon-sm"
            className="lg:hidden"
            onClick={() => setNavOpen(true)}
          >
            <Menu />
            <span className="sr-only">Open admin navigation</span>
          </Button>
          <nav aria-label="Breadcrumb" className="min-w-0">
            <ol className="flex items-center gap-1.5 text-sm">
              <li className="text-muted-foreground">
                <Link href={ROUTES.admin} className="hover:text-foreground">
                  Admin
                </Link>
              </li>
              {current.href !== ROUTES.admin && (
                <>
                  <li aria-hidden="true" className="text-muted-foreground">
                    <ChevronRight className="size-3.5" />
                  </li>
                  <li aria-current="page" className="truncate font-medium">
                    {current.label}
                  </li>
                </>
              )}
            </ol>
          </nav>
          <Button asChild variant="outline" size="sm" className="ml-auto gap-1.5">
            <Link href={ROUTES.home}>
              <MessageSquare className="size-3.5" />
              <span className="hidden sm:inline">Back to chat</span>
              <span className="sm:hidden">Chat</span>
            </Link>
          </Button>
        </header>

        <main id="admin-content" className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">{children}</div>
        </main>
      </div>

      <ApiKeysDialog open={apiKeysOpen} onOpenChange={setApiKeysOpen} />
    </div>
  )
}
