import { z } from 'zod'

/**
 * Fail fast on misconfiguration instead of surfacing it as a runtime 500 in the
 * middle of a stream. Parsed once per process on first import.
 */
const serverSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  DATABASE_URL: z.string().min(1, 'DATABASE_URL is required'),

  AUTH_SECRET: z
    .string()
    .min(32, 'AUTH_SECRET must be at least 32 characters (openssl rand -base64 32)'),
  AUTH_URL: z.string().url().optional(),
  AUTH_TRUST_HOST: z.coerce.boolean().default(true),

  // Optional OAuth — providers are registered only when both halves are present.
  AUTH_GITHUB_ID: z.string().optional(),
  AUTH_GITHUB_SECRET: z.string().optional(),

  // Optional SSO through Keycloak (or any OIDC issuer at the same paths).
  // Registered only when id, secret and issuer are all set.
  AUTH_KEYCLOAK_ID: z.string().optional(),
  AUTH_KEYCLOAK_SECRET: z.string().optional(),
  /** The issuer as browsers and tokens name it, e.g. http://localhost:8080/sso/realms/llm-dev-kit. */
  AUTH_KEYCLOAK_ISSUER: z.union([z.string().url(), z.literal('')]).optional(),
  /**
   * How this server reaches the same issuer when the public URL does not
   * resolve here (inside Docker it points back at this container).
   */
  AUTH_KEYCLOAK_INTERNAL_ISSUER: z.union([z.string().url(), z.literal('')]).optional(),

  /**
   * OpenAI-compatible endpoint. Defaults to the llm-dev-kit rag-service, which
   * exposes /v1/chat/completions with retrieval-augmented answers.
   */
  LLM_BASE_URL: z.string().url().default('http://localhost:8080/api/rag/v1'),
  /**
   * Only for a backend that is not this repo's rag-service (raw Ollama, a
   * hosted API). Unset, or a `sk-local*` placeholder, means "rag-service":
   * each request then carries the signed-in user's own access token.
   */
  LLM_API_KEY: z
    .string()
    .optional()
    .transform((value) => (value && !value.startsWith('sk-local') ? value : undefined)),
  DEFAULT_MODEL: z.string().default('llama3.1'),
  LLM_REQUEST_TIMEOUT_MS: z.coerce.number().int().positive().default(120_000),

  /** Base URLs the admin health page checks. */
  RAG_SERVICE_URL: z.string().url().default('http://localhost:8020'),
  LLM_SERVICE_URL: z.string().url().default('http://localhost:8010'),
  /** Optional: a Grafana (or other dashboard) link shown on the admin health page. */
  GRAFANA_URL: z.union([z.string().url(), z.literal('')]).optional(),

  /** `iss` and `aud` of the access tokens; must match the Python services. */
  IDENTITY_ISSUER: z.string().min(1).default('llm-dev-kit-web'),
  IDENTITY_AUDIENCE: z.string().min(1).default('llm-dev-kit'),

  /** Set false to lock the instance to existing users. */
  ALLOW_REGISTRATION: z
    .enum(['true', 'false'])
    .default('true')
    .transform((value) => value === 'true'),
})

export type ServerEnv = z.infer<typeof serverSchema>

function loadEnv(): ServerEnv {
  const parsed = serverSchema.safeParse(process.env)

  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((issue) => `  • ${issue.path.join('.')}: ${issue.message}`)
      .join('\n')
    throw new Error(`Invalid environment configuration:\n${issues}`)
  }

  return parsed.data
}

let cached: ServerEnv | null = null

export function getEnv(): ServerEnv {
  cached ??= loadEnv()
  return cached
}

export const isProduction = () => getEnv().NODE_ENV === 'production'
