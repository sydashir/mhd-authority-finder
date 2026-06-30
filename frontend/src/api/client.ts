// Typed API client — the single seam between the UI and the Phase B backend.
// The UI talks ONLY to this (never to the DB/pipeline). Base URL is env-driven.

import type { GeoLevel, Health, PageOf, Prospect, SourceTag, TrustBand } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type QueryValue = string | number | undefined

async function apiGet<T>(path: string, params?: Record<string, QueryValue>): Promise<T> {
  const url = new URL(path, API_URL)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') url.searchParams.set(key, String(value))
    }
  }
  const res = await fetch(url, { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

export interface ProspectFilters {
  contact_trust?: TrustBand
  source_tag?: SourceTag
  level?: GeoLevel
  geo?: string
  limit?: number
  offset?: number
}

export const getHealth = () => apiGet<Health>('/health')

export const getProspects = (filters: ProspectFilters) =>
  apiGet<PageOf<Prospect>>('/prospects', { ...filters })

export const getProspect = (id: number) => apiGet<Prospect>(`/prospects/${id}`)
