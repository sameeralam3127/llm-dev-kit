import 'server-only'

import { db } from '@/lib/db'
import type {
  CreateFolderInput,
  UpdateFolderInput,
} from '@/lib/validations/chat'
import { notFound } from '@/server/http'
import { toFolderDTO } from '@/server/mappers'
import type { Folder } from '@/types/chat'

export async function listFolders(userId: string): Promise<Folder[]> {
  const rows = await db.folder.findMany({
    where: { userId },
    orderBy: [{ position: 'asc' }, { createdAt: 'asc' }],
    include: { _count: { select: { chats: true } } },
  })
  return rows.map(toFolderDTO)
}

export async function createFolder(
  userId: string,
  input: CreateFolderInput,
): Promise<Folder> {
  const last = await db.folder.findFirst({
    where: { userId },
    orderBy: { position: 'desc' },
    select: { position: true },
  })

  const folder = await db.folder.create({
    data: {
      userId,
      name: input.name,
      color: input.color ?? 'slate',
      position: (last?.position ?? -1) + 1,
    },
    include: { _count: { select: { chats: true } } },
  })

  return toFolderDTO(folder)
}

export async function updateFolder(
  userId: string,
  folderId: string,
  input: UpdateFolderInput,
): Promise<Folder> {
  const existing = await db.folder.findFirst({
    where: { id: folderId, userId },
    select: { id: true },
  })
  if (!existing) throw notFound('Folder')

  const folder = await db.folder.update({
    where: { id: folderId },
    data: {
      ...(input.name === undefined ? {} : { name: input.name }),
      ...(input.color === undefined ? {} : { color: input.color }),
      ...(input.position === undefined ? {} : { position: input.position }),
    },
    include: { _count: { select: { chats: true } } },
  })

  return toFolderDTO(folder)
}

/**
 * Deleting a folder keeps its chats — they fall back to the ungrouped list via
 * the schema's `onDelete: SetNull`. Losing conversations because a label was
 * removed would be a nasty surprise.
 */
export async function deleteFolder(
  userId: string,
  folderId: string,
): Promise<void> {
  const result = await db.folder.deleteMany({ where: { id: folderId, userId } })
  if (result.count === 0) throw notFound('Folder')
}
