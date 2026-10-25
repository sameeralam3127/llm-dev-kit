import { describe, expect, it } from 'vitest'

import { isOllamaCloud } from '@/lib/models'

describe('isOllamaCloud', () => {
  it('spots the models Ollama runs on ollama.com', () => {
    for (const id of ['gpt-oss:120b-cloud', 'minimax-m2:cloud', 'gemma4:31b-cloud', 'kimi-k2-cloud']) {
      expect(isOllamaCloud(id), id).toBe(true)
    }
  })

  it('leaves local models alone, including look-alikes', () => {
    for (const id of ['llama3.1:8b', 'nomic-embed-text:latest', 'cloudy-llama', 'llama:cloudless']) {
      expect(isOllamaCloud(id), id).toBe(false)
    }
  })
})
