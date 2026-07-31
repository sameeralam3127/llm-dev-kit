'use client'

import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import * as React from 'react'

import { Sidebar } from '@/components/sidebar/sidebar'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/ui-store'

interface AppShellProps {
  user: { name: string | null; email: string | null; image: string | null }
  children: React.ReactNode
}

/**
 * Two presentations of one sidebar: a collapsible rail from `lg` up, and an
 * overlay drawer below it. The drawer closes on navigation, which is the whole
 * reason `onNavigate` is threaded down.
 */
export function AppShell({ user, children }: AppShellProps) {
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed)
  const toggleSidebar = useUiStore((state) => state.toggleSidebar)
  const mobileSidebarOpen = useUiStore((state) => state.mobileSidebarOpen)
  const setMobileSidebarOpen = useUiStore((state) => state.setMobileSidebarOpen)

  return (
    <div className="relative flex h-dvh w-full overflow-hidden bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        Skip to conversation
      </a>

      <aside
        id="sidebar"
        className={cn(
          'relative hidden shrink-0 border-r border-sidebar-border transition-[width] duration-200 lg:block',
          sidebarCollapsed ? 'w-0' : 'w-72',
        )}
        aria-hidden={sidebarCollapsed}
      >
        <div className={cn('h-full w-72', sidebarCollapsed && 'invisible')}>
          <Sidebar user={user} />
        </div>
      </aside>

      <Button
        variant="ghost"
        size="icon-sm"
        onClick={toggleSidebar}
        aria-expanded={!sidebarCollapsed}
        aria-controls="sidebar"
        className={cn(
          'absolute bottom-3 z-30 hidden bg-background/80 backdrop-blur lg:inline-flex',
          sidebarCollapsed ? 'left-2' : 'left-[16.5rem]',
          'transition-[left] duration-200',
        )}
      >
        {sidebarCollapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
        <span className="sr-only">
          {sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        </span>
      </Button>

      <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <SheetContent side="left" className="w-80 p-0 lg:hidden">
          {/* Radix requires an accessible title on every dialog surface. */}
          <SheetTitle className="sr-only">Chats</SheetTitle>
          <Sidebar user={user} onNavigate={() => setMobileSidebarOpen(false)} />
        </SheetContent>
      </Sheet>

      <main id="main-content" className="flex min-w-0 flex-1 flex-col">
        {children}
      </main>
    </div>
  )
}
