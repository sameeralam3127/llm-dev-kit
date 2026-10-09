import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => ({
  // tsconfig has `jsx: preserve` for Next; tests need JSX compiled.
  oxc: { jsx: { runtime: 'automatic' } },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    // `npm run bench` (mode "bench") runs only the timing files; normal runs skip them.
    include: mode === 'bench' ? ['src/**/*.bench.tsx'] : ['src/**/*.test.{ts,tsx}'],
    // `server-only` throws outside a React Server environment; tests import
    // client code only, so stub it rather than special-casing each file.
    alias: { 'server-only': fileURLToPath(new URL('./src/test/empty.ts', import.meta.url)) },
  },
}))
