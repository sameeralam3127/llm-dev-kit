'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/** Distance from the bottom still treated as "at the bottom", in pixels. */
const BOTTOM_THRESHOLD = 64

/**
 * Keeps a scroll container pinned to the bottom while content streams in, but
 * stops the moment the reader scrolls up — nothing is more irritating than
 * being yanked back down while reading an earlier part of the answer.
 */
export function useStickToBottom<T extends HTMLElement>(dependency: unknown) {
  const ref = useRef<T | null>(null)
  const [isPinned, setIsPinned] = useState(true)
  const isPinnedRef = useRef(true)
  isPinnedRef.current = isPinned

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const element = ref.current
    if (!element) return

    element.scrollTo({ top: element.scrollHeight, behavior })
    setIsPinned(true)
  }, [])

  const handleScroll = useCallback(() => {
    const element = ref.current
    if (!element) return

    const distance =
      element.scrollHeight - element.scrollTop - element.clientHeight
    setIsPinned(distance <= BOTTOM_THRESHOLD)
  }, [])

  useEffect(() => {
    const element = ref.current
    if (!element) return

    element.addEventListener('scroll', handleScroll, { passive: true })
    return () => element.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  // Follow new content only while pinned. `auto` avoids queueing a smooth
  // animation per token, which would never catch up with a fast stream.
  useEffect(() => {
    if (!isPinnedRef.current) return
    const element = ref.current
    if (!element) return

    element.scrollTop = element.scrollHeight
  }, [dependency])

  return { ref, isPinned, scrollToBottom }
}
