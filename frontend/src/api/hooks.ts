// TanStack Query hooks over the typed client. keepPreviousData keeps lists
// populated while a new page/filter loads (no flash to empty).

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getHealth, getProspects, getRuns, getStats, triggerRun, type ProspectFilters } from './client'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: false,
  })
}

export function useStats() {
  return useQuery({ queryKey: ['stats'], queryFn: getStats })
}

export function useProspects(filters: ProspectFilters) {
  return useQuery({
    queryKey: ['prospects', filters],
    queryFn: () => getProspects(filters),
    placeholderData: keepPreviousData,
  })
}

export function useRuns(limit = 50) {
  return useQuery({
    queryKey: ['runs', limit],
    queryFn: () => getRuns({ limit }),
    // Poll every 2s while any run is still running; stop once all are terminal.
    refetchInterval: (query) =>
      query.state.data?.items.some((r) => r.status === 'running') ? 2000 : false,
    placeholderData: keepPreviousData,
  })
}

export function useTriggerRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: triggerRun,
    onSuccess: () => {
      // Surface the new 'running' row immediately; polling takes over from there.
      void queryClient.invalidateQueries({ queryKey: ['runs'] })
    },
  })
}
