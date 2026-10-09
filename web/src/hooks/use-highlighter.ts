'use client'

import type { Options } from 'react-markdown'
import { useEffect, useState } from 'react'

type RehypePlugin = NonNullable<Options['rehypePlugins']>[number]

let loaded: RehypePlugin | null = null
let loading: Promise<RehypePlugin> | null = null

/** Start (or join) loading the highlighter chunk. */
export function loadHighlighter(): Promise<RehypePlugin> {
  loading ??= import('@/components/markdown/highlight').then((module) => {
    loaded = module.rehypeHighlightPlugin
    return loaded
  })
  return loading
}

/**
 * The rehype highlight plugin once its chunk has loaded, otherwise `null`.
 *
 * Loads on first use, and only when `needed` (the content has a code block).
 * The first render is always unhighlighted on a fresh page, matching the
 * server render, so hydration never mismatches; colours arrive a moment later.
 */
export function useHighlighter(needed: boolean): RehypePlugin | null {
  const [plugin, setPlugin] = useState<RehypePlugin | null>(() => loaded)

  useEffect(() => {
    if (!needed || plugin) return
    let active = true
    void loadHighlighter().then((next) => {
      if (active) setPlugin(() => next)
    })
    return () => {
      active = false
    }
  }, [needed, plugin])

  return needed ? plugin : null
}
