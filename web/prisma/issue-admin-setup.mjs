import { randomBytes } from 'node:crypto'
import { PrismaClient } from '@prisma/client'

import { hashSetupCode, SETUP_CODE_MINUTES, SETUP_ID } from './setup-code.mjs'

if (!process.stdin.isTTY || !process.stdout.isTTY) {
  console.error('Run this command from an interactive terminal.')
  process.exit(1)
}

const email = process.argv[2]?.trim().toLowerCase()
const emailPattern = /^[^\s@\0]+@[^\s@\0]+\.[^\s@\0]+$/
if (process.argv.length !== 3 || !email || email.length > 254 || !emailPattern.test(email)) {
  console.error('Usage: node prisma/issue-admin-setup.mjs <admin-email>')
  process.exit(1)
}

if (!process.env.DATABASE_URL) {
  console.error('Set DATABASE_URL for the running web instance before issuing a setup code.')
  process.exit(1)
}

const db = new PrismaClient()
try {
  const code = randomBytes(24).toString('base64url')
  const hash = await hashSetupCode(code, email)
  const result = await db.$transaction(async (tx) => {
    const admin = await tx.user.findFirst({ where: { role: 'admin' }, select: { id: true } })
    if (admin) return 'has-admin'

    const { count } = await tx.setupCode.updateMany({
      where: { id: SETUP_ID },
      data: {
        hash,
        expiresAt: new Date(Date.now() + SETUP_CODE_MINUTES * 60_000),
      },
    })
    return count === 1 ? 'issued' : 'uninitialized'
  }, { isolationLevel: 'Serializable' })

  if (result === 'issued') {
    console.log(`Setup code (expires in ${SETUP_CODE_MINUTES} minutes): ${code}`)
  } else {
    console.error(
      result === 'has-admin'
        ? 'This instance already has an administrator.'
        : 'Start the web instance and wait for it to initialize before issuing a setup code.',
    )
    process.exitCode = 1
  }
} catch {
  console.error('Could not issue a setup code. Check the web database and retry.')
  process.exitCode = 1
} finally {
  await db.$disconnect()
}
