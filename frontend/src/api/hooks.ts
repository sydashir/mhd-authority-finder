// TanStack Query hooks over the typed client. keepPreviousData keeps the table
// populated while a new page/filter loads (no flash to empty).

import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { getHealth, getProspects, type ProspectFilters } from './client'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: false,
  })
}

export function useProspects(filters: ProspectFilters) {
  return useQuery({
    queryKey: ['prospects', filters],
    queryFn: () => getProspects(filters),
    placeholderData: keepPreviousData,
  })
}
