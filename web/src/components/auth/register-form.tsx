'use client'

import { AlertCircle, Loader2 } from 'lucide-react'
import { signIn } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import * as React from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api-client'
import { registerSchema } from '@/lib/validations/auth'

interface RegisterFormProps {
  callbackUrl: string
}

export function RegisterForm({ callbackUrl }: RegisterFormProps) {
  const router = useRouter()
  const [isPending, setIsPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({})

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    setFieldErrors({})

    const formData = new FormData(event.currentTarget)
    const parsed = registerSchema.safeParse({
      name: formData.get('name'),
      email: formData.get('email'),
      password: formData.get('password'),
    })

    if (!parsed.success) {
      const errors: Record<string, string> = {}
      for (const issue of parsed.error.issues) {
        const key = issue.path[0]
        if (typeof key === 'string' && !errors[key]) errors[key] = issue.message
      }
      setFieldErrors(errors)
      return
    }

    setIsPending(true)

    try {
      await api.auth.register(parsed.data)
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Could not create your account',
      )
      setIsPending(false)
      return
    }

    // Sign in straight away — making someone re-type what they just entered is
    // a pointless extra step.
    const result = await signIn('credentials', {
      email: parsed.data.email,
      password: parsed.data.password,
      redirect: false,
    })

    if (result?.error) {
      setError('Account created, but sign-in failed. Try signing in manually.')
      setIsPending(false)
      return
    }

    router.push(callbackUrl)
    router.refresh()
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          name="name"
          autoComplete="name"
          placeholder="Ada Lovelace"
          required
          aria-invalid={Boolean(fieldErrors['name'])}
          aria-describedby={fieldErrors['name'] ? 'name-error' : undefined}
        />
        {fieldErrors['name'] && (
          <p id="name-error" className="text-xs text-destructive">
            {fieldErrors['name']}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          required
          aria-invalid={Boolean(fieldErrors['email'])}
          aria-describedby={fieldErrors['email'] ? 'email-error' : undefined}
        />
        {fieldErrors['email'] && (
          <p id="email-error" className="text-xs text-destructive">
            {fieldErrors['email']}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          aria-invalid={Boolean(fieldErrors['password'])}
          aria-describedby="password-hint"
        />
        <p
          id="password-hint"
          className={
            fieldErrors['password']
              ? 'text-xs text-destructive'
              : 'text-xs text-muted-foreground'
          }
        >
          {fieldErrors['password'] ??
            'At least 10 characters, including a letter and a number.'}
        </p>
      </div>

      <Button type="submit" className="w-full gap-2" disabled={isPending}>
        {isPending && <Loader2 className="size-4 animate-spin" />}
        {isPending ? 'Creating account…' : 'Create account'}
      </Button>
    </form>
  )
}
