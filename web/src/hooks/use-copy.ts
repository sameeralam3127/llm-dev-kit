'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

import { copyToClipboard } from '@/lib/utils'

export function useCopy(resetAfterMs = 2000) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [])

  const copy = useCallback(
    async (text: string, successMessage?: string) => {
      const ok = await copyToClipboard(text)

      if (!ok) {
        toast.error('Could not copy to clipboard')
        return false
      }

      setCopied(true)
      if (successMessage) toast.success(successMessage)

      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => setCopied(false), resetAfterMs)
      return true
    },
    [resetAfterMs],
  )

  return { copied, copy }
}
