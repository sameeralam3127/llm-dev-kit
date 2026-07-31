import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

const db = new PrismaClient()

const DEMO_EMAIL = process.env['SEED_EMAIL'] ?? 'demo@example.com'
const DEMO_PASSWORD = process.env['SEED_PASSWORD'] ?? 'demo-password-1'
const DEFAULT_MODEL = process.env['DEFAULT_MODEL'] ?? 'llama3.1'

async function main() {
  const passwordHash = await bcrypt.hash(DEMO_PASSWORD, 12)

  // Idempotent: re-running the seed refreshes the password rather than failing
  // on the unique email constraint.
  const user = await db.user.upsert({
    where: { email: DEMO_EMAIL },
    update: { passwordHash },
    create: {
      email: DEMO_EMAIL,
      name: 'Demo User',
      passwordHash,
    },
  })

  const existingChats = await db.chat.count({ where: { userId: user.id } })
  if (existingChats > 0) {
    console.log(`Seed: ${DEMO_EMAIL} already has ${existingChats} chats — skipping.`)
    return
  }

  const folder = await db.folder.create({
    data: { userId: user.id, name: 'Getting started', color: 'sky', position: 0 },
  })

  await db.chat.create({
    data: {
      userId: user.id,
      folderId: folder.id,
      title: 'Welcome to LLM Dev Kit',
      model: DEFAULT_MODEL,
      messages: {
        create: [
          {
            role: 'user',
            content: 'What can this workspace do?',
            position: 0,
          },
          {
            role: 'assistant',
            model: DEFAULT_MODEL,
            position: 1,
            content: [
              'A few things worth trying:',
              '',
              '- **Streaming answers** — responses render token by token, and you can stop one mid-flight.',
              '- **Folders** — group related chats; deleting a folder keeps its chats.',
              '- **Edit & regenerate** — editing a message rewinds the conversation to that point; previous answers are kept and reachable with the `‹ 1/2 ›` control.',
              '- **Sharing** — publish a read-only link to any conversation, and revoke it later.',
              '',
              'Code blocks are highlighted and copyable:',
              '',
              '```python',
              'def greet(name: str) -> str:',
              '    return f"Hello, {name}!"',
              '```',
            ].join('\n'),
          },
        ],
      },
    },
  })

  console.log(`Seed complete. Sign in as ${DEMO_EMAIL} / ${DEMO_PASSWORD}`)
}

main()
  .catch((error) => {
    console.error(error)
    process.exit(1)
  })
  .finally(() => {
    void db.$disconnect()
  })
