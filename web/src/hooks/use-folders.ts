'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api, queryKeys } from '@/lib/api-client'
import type { CreateFolderInput, UpdateFolderInput } from '@/lib/validations/chat'

export function useFolders() {
  return useQuery({
    queryKey: queryKeys.folders(),
    queryFn: ({ signal }) => api.folders.list(signal),
    staleTime: 60_000,
  })
}

export function useCreateFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: CreateFolderInput) => api.folders.create(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.folders() })
      toast.success('Folder created')
    },
    onError: (error: Error) => {
      toast.error('Could not create folder', { description: error.message })
    },
  })
}

export function useUpdateFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ folderId, input }: { folderId: string; input: UpdateFolderInput }) =>
      api.folders.update(folderId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.folders() })
    },
    onError: (error: Error) => {
      toast.error('Could not update folder', { description: error.message })
    },
  })
}

export function useDeleteFolder() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (folderId: string) => api.folders.remove(folderId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.folders() })
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
      toast.success('Folder deleted', { description: 'Its chats moved to All chats.' })
    },
    onError: (error: Error) => {
      toast.error('Could not delete folder', { description: error.message })
    },
  })
}
