// TypeScript mirror of the backend Pydantic response models (backend/schemas.py).
// Keep these in lockstep with the API contract (ADR-014/015).

export type TrustBand = 'high' | 'medium' | 'low'
export type SourceTag = 'MHD' | 'AH'
export type GeoLevel = 'state' | 'county' | 'city'
export type RunStatus = 'running' | 'success' | 'failed'

export interface Prospect {
  id: number
  website: string
  specific_page: string
  email: string
  phone: string
  contact_source: string
  contact_trust: TrustBand
  organization_description: string
  geo_served: string
  population: number | null
  competitor_links: string
  source_tag: SourceTag
  confidence: TrustBand
  date_added: string
  created_at: string
  updated_at: string
  run_id: number | null
  geo_id: number | null
}

export interface PageOf<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Run {
  id: number
  site: string
  status: RunStatus
  started_at: string
  finished_at: string | null
  geos_processed: number
  rows_written: number
  billed_searches: number
  error_summary: string | null
}

export type RunSite = 'mhd' | 'ah' | 'both'
export type RunMode = 'incremental' | 'full'

export interface RunAccepted {
  run_id: number
  status: RunStatus
}

export interface Health {
  status: string
  database: string
}

export interface Stats {
  total_prospects: number
  high_trust: number
  with_email: number
  geos_covered: number
  last_run: Run | null
}
