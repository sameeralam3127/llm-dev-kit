'use client'

import { Button } from '@/components/ui/button'
import { useUiStore } from '@/stores/ui-store'

/** Opens the mobile drawer from a server-rendered header. */
export function MobileSidebarTrigger({ children }: { children: React.ReactNode }) {
  const setMobileSidebarOpen = useUiStore((state) => state.setMobileSidebarOpen)

  return (
    <Button variant="ghost" size="icon" onClick={() => setMobileSidebarOpen(true)}>
      {children}
    </Button>
  )
}
