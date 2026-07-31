'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

import { api, type ListChatsParams, queryKeys } from '@/lib/api-client'
import { ROUTES } from '@/lib/constants'
import type { UpdateChatInput } from '@/lib/validations/chat'
import type { ChatSummary } from '@/types/chat'

export function useChats(params: ListChatsParams = {}) {
  return useQuery({
    queryKey: queryKeys.chats(params),
    queryFn: ({ signal }) => api.chats.list(params, signal),
    staleTime: 15_000,
  })
}

export function useCreateChat() {
  const queryClient = useQueryClient()
  const router = useRouter()

  return useMutation({
    mutationFn: api.chats.create,
    onSuccess: (chat) => {
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
      router.push(ROUTES.chat(chat.id))
    },
    onError: (error: Error) => {
      toast.error('Could not start a new chat', { description: error.message })
    },
  })
}

export function useUpdateChat() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ chatId, input }: { chatId: string; input: UpdateChatInput }) =>
      api.chats.update(chatId, input),

    // Renaming, pinning and moving should feel instant; the list is small and
    // the request is a single row update, so an optimistic patch is safe.
    onMutate: async ({ chatId, input }) => {
      await queryClient.cancelQueries({ queryKey: ['chats'] })
      const snapshot = queryClient.getQueriesData<ChatSummary[]>({
        queryKey: ['chats'],
      })

      queryClient.setQueriesData<ChatSummary[]>({ queryKey: ['chats'] }, (old) =>
        old?.map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                ...(input.title === undefined ? {} : { title: input.title }),
                ...(input.pinned === undefined ? {} : { pinned: input.pinned }),
                ...(input.archived === undefined ? {} : { archived: input.archived }),
                ...(input.folderId === undefined ? {} : { folderId: input.folderId }),
                ...(input.model === undefined ? {} : { model: input.model }),
              }
            : chat,
        ),
      )

      return { snapshot }
    },

    onError: (error: Error, _variables, context) => {
      context?.snapshot.forEach(([key, value]) => {
        queryClient.setQueryData(key, value)
      })
      toast.error('Update failed', { description: error.message })
    },

    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
      void queryClient.invalidateQueries({ queryKey: queryKeys.chat(variables.chatId) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.folders() })
    },
  })
}

export function useDeleteChat() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (chatId: string) => api.chats.remove(chatId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
      void queryClient.invalidateQueries({ queryKey: queryKeys.folders() })
      toast.success('Chat deleted')
    },
    onError: (error: Error) => {
      toast.error('Could not delete chat', { description: error.message })
    },
  })
}
