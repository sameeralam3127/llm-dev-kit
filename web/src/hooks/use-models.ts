'use client'

import { useQuery } from '@tanstack/react-query'

import { api, queryKeys } from '@/lib/api-client'

export function useModels() {
  return useQuery({
    queryKey: queryKeys.models(),
    queryFn: ({ signal }) => api.models.list(signal),
    // The model list only changes when someone pulls a new one on the host.
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
