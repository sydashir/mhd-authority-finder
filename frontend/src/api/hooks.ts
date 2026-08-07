// TanStack Query hooks over the typed client. keepPreviousData keeps lists
// populated while a new page/filter loads (no flash to empty).

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  getDomainStats,
  getHealth,
  getMe,
  getProspects,
  getReviewQueue,
  getRuns,
  getStats,
  patchDomainReview,
  patchOutreach,
  triggerRun,
  type ProspectFilters,
} from './client'
import type { OutreachStatus } from './types'

export function useMe() {
  // 401 -> not signed in (isError, no retry). Drives the auth gate.
  return useQuery({ queryKey: ['me'], queryFn: getMe, retry: false, staleTime: 5 * 60_000 })
}

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

export function useSetOutreach() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; status: OutreachStatus; notes?: string }) =>
      patchOutreach(vars.id, { status: vars.status, notes: vars.notes }),
    onSuccess: () => {
      // The row's pill + the dashboard's outreach counts both reflect the change.
      void queryClient.invalidateQueries({ queryKey: ['prospects'] })
      void queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })
}


export function useReviewQueue(params: { limit?: number; offset?: number } = {}) {
  return useQuery({
    queryKey: ['domains', 'review', params],
    queryFn: () => getReviewQueue(params),
    placeholderData: keepPreviousData,
  })
}

export function useDomainStats() {
  return useQuery({ queryKey: ['domains', 'stats'], queryFn: getDomainStats })
}

export function useReviewDomain() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: number; approve: boolean; bucket?: string | null }) =>
      patchDomainReview(vars.id, { approve: vars.approve, bucket: vars.bucket }),
    onSuccess: () => {
      // The queue shrinks and the header counts move; an approval also changes what a
      // future re-classification would put in the sheet, so prospects are refreshed too.
      void queryClient.invalidateQueries({ queryKey: ['domains'] })
      void queryClient.invalidateQueries({ queryKey: ['prospects'] })
    },
  })
}
