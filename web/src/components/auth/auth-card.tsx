import { cn } from '@/lib/utils'

interface AuthCardProps {
  title: string
  description: string
  children: React.ReactNode
  footer?: React.ReactNode
  className?: string
}

export function AuthCard({
  title,
  description,
  children,
  footer,
  className,
}: AuthCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-card p-6 shadow-sm',
        className,
      )}
    >
      <div className="mb-5">
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>

      {children}

      {footer && (
        <div className="mt-5 border-t border-border pt-4 text-center text-sm text-muted-foreground">
          {footer}
        </div>
      )}
    </div>
  )
}
