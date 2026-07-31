import { Sparkles } from 'lucide-react'

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-3 flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Sparkles className="size-5" />
          </div>
          <h1 className="text-lg font-semibold tracking-tight">LLM Dev Kit</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Your local-first AI chat workspace
          </p>
        </div>

        {children}
      </div>
    </div>
  )
}
