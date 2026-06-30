// Typed API client — the single seam between the UI and the Phase B backend.
// The UI talks ONLY to this (never to the DB/pipeline). Base URL is env-driven.

import type { GeoLevel, Health, PageOf, Prospect, SourceTag, Stats, TrustBand } from './types'

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

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(new URL(path, API_URL), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
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

export const getStats = () => apiGet<Stats>('/stats')

export const getProspects = (filters: ProspectFilters) =>
  apiGet<PageOf<Prospect>>('/prospects', { ...filters })

/** Every prospect matching the filters, paged through the API's 200-row cap. */
export async function getAllProspects(filters: ProspectFilters): Promise<Prospect[]> {
  const all: Prospect[] = []
  const limit = 200
  let offset = 0
  for (;;) {
    const page = await getProspects({ ...filters, limit, offset })
    all.push(...page.items)
    offset += limit
    if (offset >= page.total || page.items.length === 0) break
  }
  return all
}

export const getProspect = (id: number) => apiGet<Prospect>(`/prospects/${id}`)

export interface ExportResult {
  url: string
  spreadsheet_id: string
  row_count: number
}

/** Export the current filtered view to a FRESH Google Sheet (never the master). */
export const exportSheet = (filters: ProspectFilters) =>
  apiPost<ExportResult>('/export/sheet', filters)
