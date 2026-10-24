'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api, queryKeys } from '@/lib/api-client'
import type { Role } from '@/lib/roles'

export function useAdminUsers() {
  return useQuery({
    queryKey: queryKeys.adminUsers(),
    queryFn: ({ signal }) => api.admin.users(signal),
  })
}

export function useSetRole() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      api.admin.setRole(userId, role),
    onSuccess: (user) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers() })
      toast.success(`${user.name ?? user.email} is now ${user.role === 'admin' ? 'an' : 'a'} ${user.role}`)
    },
    onError: (error: Error) => {
      toast.error('Could not change the role', { description: error.message })
    },
  })
}

export function useAdminHealth() {
  return useQuery({
    queryKey: queryKeys.adminHealth(),
    queryFn: ({ signal }) => api.admin.health(signal),
    refetchInterval: 30_000,
  })
}

export function useAdminOverview() {
  return useQuery({
    queryKey: queryKeys.adminOverview(),
    queryFn: ({ signal }) => api.admin.overview(signal),
    refetchInterval: 60_000,
  })
}

export function useAdminApiKeys() {
  return useQuery({
    queryKey: queryKeys.adminApiKeys(),
    queryFn: ({ signal }) => api.admin.apiKeys(signal),
  })
}

export function useRevokeAnyApiKey() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (key: { id: string; name: string }) => api.admin.revokeApiKey(key.id),
    onSuccess: (_, key) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminApiKeys() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminOverview() })
      void queryClient.invalidateQueries({ queryKey: queryKeys.adminUsers() })
      toast.success(`Revoked “${key.name}”`, { description: 'It stops working within a minute.' })
    },
    onError: (error: Error) => {
      toast.error('Could not revoke the key', { description: error.message })
    },
  })
}

export function useAdminDocuments() {
  return useQuery({
    queryKey: queryKeys.adminDocuments(),
    queryFn: ({ signal }) => api.admin.documents(signal),
  })
}

/** Invalidate everything a change to the index or cache shows up in. */
function useRefreshDocuments() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.adminDocuments() })
    void queryClient.invalidateQueries({ queryKey: queryKeys.adminHealth() })
  }
}

export function useUploadDocument() {
  const refresh = useRefreshDocuments()

  return useMutation({
    mutationFn: (file: File) => api.admin.uploadDocument(file),
    onSuccess: (result) => {
      refresh()
      toast.success(`Indexed ${result.filename}`, {
        description: `${result.chunks} chunk${result.chunks === 1 ? '' : 's'} added; cached answers cleared.`,
      })
    },
    onError: (error: Error, file) => {
      toast.error(`Could not index ${file.name}`, { description: error.message })
    },
  })
}

export function useClearDocuments() {
  const refresh = useRefreshDocuments()

  return useMutation({
    mutationFn: () => api.admin.clearDocuments(),
    onSuccess: () => {
      refresh()
      toast.success('Every document was removed from the index')
    },
    onError: (error: Error) => {
      toast.error('Could not clear the index', { description: error.message })
    },
  })
}

export function useClearCache() {
  const refresh = useRefreshDocuments()

  return useMutation({
    mutationFn: () => api.admin.clearCache(),
    onSuccess: ({ cleared }) => {
      refresh()
      toast.success(`Cleared ${cleared} cached answer${cleared === 1 ? '' : 's'}`)
    },
    onError: (error: Error) => {
      toast.error('Could not clear the cache', { description: error.message })
    },
  })
}
