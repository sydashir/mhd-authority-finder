// Typed API client — the single seam between the UI and the Phase B backend.
// The UI talks ONLY to this (never to the DB/pipeline). Base URL is env-driven.

import type {
  AuthUser,
  DomainStats,
  GeoLevel,
  Health,
  LinkDomain,
  OutreachStatus,
  PageOf,
  Prospect,
  Run,
  RunAccepted,
  RunMode,
  RunSite,
  SourceTag,
  Stats,
  TrustBand,
} from './types'

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

/** Build an ApiError, preferring the API's JSON ``detail`` message (e.g. a 409's reason). */
async function errorFrom(res: Response): Promise<ApiError> {
  let message = `${res.status} ${res.statusText}`
  try {
    const body: unknown = await res.json()
    if (body && typeof (body as { detail?: unknown }).detail === 'string') {
      message = (body as { detail: string }).detail
    }
  } catch {
    // non-JSON error body — keep the status line
  }
  return new ApiError(res.status, message)
}

async function apiGet<T>(path: string, params?: Record<string, QueryValue>): Promise<T> {
  const url = new URL(path, API_URL)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== '') url.searchParams.set(key, String(value))
    }
  }
  // credentials:'include' sends the session cookie (backend CORS allows credentials).
  const res = await fetch(url, { headers: { Accept: 'application/json' }, credentials: 'include' })
  if (!res.ok) throw await errorFrom(res)
  return (await res.json()) as T
}

async function apiSend<T>(method: 'POST' | 'PATCH', path: string, body: unknown): Promise<T> {
  const res = await fetch(new URL(path, API_URL), {
    method,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
    credentials: 'include',
  })
  if (!res.ok) throw await errorFrom(res)
  return (await res.json()) as T
}

const apiPost = <T>(path: string, body: unknown) => apiSend<T>('POST', path, body)
const apiPatch = <T>(path: string, body: unknown) => apiSend<T>('PATCH', path, body)

export interface ProspectFilters {
  contact_trust?: TrustBand
  source_tag?: SourceTag
  level?: GeoLevel
  geo?: string
  outreach_status?: OutreachStatus
  search?: string
  sort?: string
  sort_dir?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export const getHealth = () => apiGet<Health>('/health')

// --- auth (ADR-018) ---
export const getMe = () => apiGet<AuthUser>('/auth/me')
export const postLogin = (username: string, password: string) =>
  apiPost<AuthUser>('/auth/login', { username, password })
export const postLogout = () => apiPost<{ ok: boolean }>('/auth/logout', {})

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

/** Set a prospect's outreach status/notes (ADR-022) — the backend records the signed-in user. */
export const patchOutreach = (id: number, body: { status: OutreachStatus; notes?: string }) =>
  apiPatch<Prospect>(`/prospects/${id}/outreach`, body)

export interface ExportResult {
  url: string
  spreadsheet_id: string
  row_count: number
}

/** Export the current filtered view to a FRESH Google Sheet (never the master). */
export const exportSheet = (filters: ProspectFilters) =>
  apiPost<ExportResult>('/export/sheet', filters)

export const getReviewQueue = (params: { limit?: number; offset?: number } = {}) =>
  apiGet<PageOf<LinkDomain>>('/domains/review', { ...params })

export const getDomainStats = () => apiGet<DomainStats>('/domains/stats')

/** Accept or reject a proposed domain. Approval is the ONLY way one reaches the client sheet. */
export const patchDomainReview = (id: number, body: { approve: boolean; bucket?: string | null }) =>
  apiPatch<LinkDomain>(`/domains/${id}/review`, body)

export const getRuns = (params: { limit?: number; offset?: number } = {}) =>
  apiGet<PageOf<Run>>('/runs', { ...params })

export interface RunTrigger {
  site: RunSite
  mode: RunMode
}

/** Start a pipeline run — returns immediately (202) with the run_id to poll. */
export const triggerRun = (body: RunTrigger) => apiPost<RunAccepted>('/runs', body)
