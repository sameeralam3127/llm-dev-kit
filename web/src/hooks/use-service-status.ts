'use client'

import { useQuery } from '@tanstack/react-query'

import { api, queryKeys } from '@/lib/api-client'

/** Polls whether answers can be generated, so the chat can say so before a send fails. */
export function useServiceStatus() {
  const query = useQuery({
    queryKey: queryKeys.status(),
    queryFn: ({ signal }) => api.status.get(signal),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 10_000,
    retry: false,
  })
  // Unknown (still loading, or the status check itself failed) is not offline:
  // only a definite answer changes what the chat shows.
  return { offline: query.data?.modelHost === 'offline', refresh: query.refetch }
}
