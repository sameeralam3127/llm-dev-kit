import { z } from 'zod'

import { FOLDER_COLOR_IDS, LIMITS } from '@/lib/constants'

export const MessageRoleSchema = z.enum(['user', 'assistant', 'system'])

export const cuidSchema = z.string().min(1).max(64)

export const sendMessageSchema = z
  .object({
    chatId: cuidSchema,
    content: z.string().trim().min(1).max(LIMITS.messageMaxChars).optional(),
    intent: z.enum(['send', 'regenerate', 'edit']),
    targetMessageId: cuidSchema.optional(),
    model: z.string().min(1).max(200).optional(),
  })
  .superRefine((value, ctx) => {
    if (value.intent === 'send' && !value.content) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['content'],
        message: 'content is required when sending a message',
      })
    }
    if (value.intent === 'edit') {
      if (!value.content) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['content'],
          message: 'content is required when editing a message',
        })
      }
      if (!value.targetMessageId) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ['targetMessageId'],
          message: 'targetMessageId is required when editing a message',
        })
      }
    }
  })

export const createChatSchema = z.object({
  title: z.string().trim().min(1).max(LIMITS.titleMaxChars).optional(),
  model: z.string().min(1).max(200).optional(),
  folderId: cuidSchema.nullable().optional(),
  systemPrompt: z.string().max(LIMITS.systemPromptMaxChars).nullable().optional(),
})

export const updateChatSchema = z
  .object({
    title: z.string().trim().min(1).max(LIMITS.titleMaxChars).optional(),
    model: z.string().min(1).max(200).optional(),
    folderId: cuidSchema.nullable().optional(),
    systemPrompt: z.string().max(LIMITS.systemPromptMaxChars).nullable().optional(),
    pinned: z.boolean().optional(),
    archived: z.boolean().optional(),
    shared: z.boolean().optional(),
  })
  .refine((value) => Object.keys(value).length > 0, {
    message: 'No fields to update',
  })

export const createFolderSchema = z.object({
  name: z.string().trim().min(1).max(LIMITS.folderNameMaxChars),
  color: z.enum(FOLDER_COLOR_IDS).optional(),
})

export const updateFolderSchema = z
  .object({
    name: z.string().trim().min(1).max(LIMITS.folderNameMaxChars).optional(),
    color: z.enum(FOLDER_COLOR_IDS).optional(),
    position: z.number().int().min(0).max(10_000).optional(),
  })
  .refine((value) => Object.keys(value).length > 0, {
    message: 'No fields to update',
  })

export const listChatsQuerySchema = z.object({
  q: z.string().trim().max(200).optional(),
  folderId: z.string().max(64).optional(),
  archived: z
    .enum(['true', 'false'])
    .optional()
    .transform((value) => value === 'true'),
})

export type SendMessageInput = z.infer<typeof sendMessageSchema>
export type CreateChatInput = z.infer<typeof createChatSchema>
export type UpdateChatInput = z.infer<typeof updateChatSchema>
export type CreateFolderInput = z.infer<typeof createFolderSchema>
export type UpdateFolderInput = z.infer<typeof updateFolderSchema>
