// Switch the Prisma datasource provider before `prisma generate`:
//
//   node prisma/use-provider.mjs postgresql [path/to/schema.prisma]
//
// The schema in the repository stays on SQLite, the default. The web image's
// build runs this with its DATABASE_PROVIDER build argument, so the lite
// profile's image talks to Postgres. Do not commit a switched schema.
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const PROVIDERS = new Set(['sqlite', 'postgresql'])
const [provider, path = fileURLToPath(new URL('./schema.prisma', import.meta.url))] =
  process.argv.slice(2)

if (!PROVIDERS.has(provider)) {
  console.error(`Unknown provider "${provider}"; expected one of: ${[...PROVIDERS].join(', ')}`)
  process.exit(1)
}

const schema = readFileSync(path, 'utf8')
const datasource = /(datasource db \{\s*provider = )"[^"]+"/
if (!datasource.test(schema)) {
  console.error(`No datasource provider line in ${path}`)
  process.exit(1)
}
writeFileSync(path, schema.replace(datasource, `$1"${provider}"`))
