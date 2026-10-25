/**
 * Ollama names the models it runs on ollama.com, not locally, with a `cloud`
 * tag or a `-cloud` suffix (`gpt-oss:120b-cloud`, `minimax-m2:cloud`). Same
 * rule as model-gateway's `is_ollama_cloud`.
 */
export function isOllamaCloud(id: string): boolean {
  const [base = '', tag = ''] = id.trim().toLowerCase().split(':', 2)
  return tag === 'cloud' || tag.endsWith('-cloud') || base.endsWith('-cloud')
}
