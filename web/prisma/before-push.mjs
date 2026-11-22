// Runs before `prisma db push`. Message (chatId, position) is unique, and
// databases written before that rule may hold duplicates. `db push` will not
// add a unique index to an existing table without --accept-data-loss, a flag
// that would also let future pushes drop data silently. So this renumbers the
// chats that have duplicates, keeping their order (position, then creation
// time, then id), and creates the index itself; the push then has nothing to
// do. Positions may have gaps, so other chats keep theirs. Safe to run on a
// fresh database and on every start.
import { PrismaClient } from '@prisma/client'

const url = process.env.DATABASE_URL ?? ''
// SQLite only: sqlite_master does not exist elsewhere, and failing here would
// stop the container from starting after a switch to another database.
if (!url.startsWith('file:')) process.exit(0)

// One connection: the ranking lives in a temporary table, which is per connection.
const db = new PrismaClient({
  datasourceUrl: url.includes('connection_limit=') ? url : `${url}${url.includes('?') ? '&' : '?'}connection_limit=1`,
})
try {
  const [table] = await db.$queryRawUnsafe(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'Message'",
  )
  if (table) {
    // Rank first, then update: ranking inside the UPDATE would see rows it has
    // already changed.
    await db.$executeRawUnsafe('DROP TABLE IF EXISTS temp.message_ranks')
    await db.$executeRawUnsafe(`
      CREATE TEMP TABLE message_ranks AS
      SELECT "id", ROW_NUMBER() OVER (
               PARTITION BY "chatId" ORDER BY "position", "createdAt", "id"
             ) - 1 AS rn
        FROM "Message"
       WHERE "chatId" IN (
         SELECT "chatId" FROM "Message" GROUP BY "chatId", "position" HAVING COUNT(*) > 1
       )`)
    const fixed = await db.$executeRawUnsafe(`
      UPDATE "Message"
         SET "position" = (SELECT rn FROM message_ranks WHERE message_ranks."id" = "Message"."id")
       WHERE "id" IN (SELECT "id" FROM message_ranks)`)
    await db.$executeRawUnsafe('DROP TABLE temp.message_ranks')
    if (fixed > 0) console.log(`Renumbered ${fixed} messages in chats that had duplicate positions.`)
    await db.$executeRawUnsafe(
      'CREATE UNIQUE INDEX IF NOT EXISTS "Message_chatId_position_key" ON "Message"("chatId", "position")',
    )
    await db.$executeRawUnsafe('DROP INDEX IF EXISTS "Message_chatId_position_idx"')
  }
} finally {
  await db.$disconnect()
}
