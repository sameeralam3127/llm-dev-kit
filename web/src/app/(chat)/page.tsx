import { Menu } from 'lucide-react'

import { NewChatLauncher } from '@/components/chat/new-chat-launcher'
import { MobileSidebarTrigger } from '@/components/layout/mobile-sidebar-trigger'

export const dynamic = 'force-dynamic'

export default function ChatHomePage() {
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3 lg:hidden">
        <MobileSidebarTrigger>
          <Menu />
          <span className="sr-only">Open chat list</span>
        </MobileSidebarTrigger>
        <span className="text-sm font-semibold">LLM Dev Kit</span>
      </header>

      <NewChatLauncher />
    </div>
  )
}
