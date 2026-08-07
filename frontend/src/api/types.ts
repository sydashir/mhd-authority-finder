// TypeScript mirror of the backend Pydantic response models (backend/schemas.py).
// Keep these in lockstep with the API contract (ADR-014/015).

export type TrustBand = 'high' | 'medium' | 'low'
export type SourceTag = 'MHD' | 'AH' | 'Both'
export type GeoLevel = 'state' | 'county' | 'city'
export type RunStatus = 'running' | 'success' | 'failed'
export type OutreachStatus =
  | 'not_contacted'
  | 'contacted'
  | 'responded'
  | 'interested'
  | 'not_interested'
  | 'linked'
  | 'bounced'

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
  contact_found_on: string
  /** Ahrefs DR, authority-sourced rows only. null for .gov/.edu — never scored (ADR-027). */
  domain_rating: number | null
  /** Wider link classes (ADR-039); semicolon-joined, "—" when checked and none found.
   *  competitor_links keeps its own contractual meaning: the brief's 16. */
  addiction_directories: string
  mental_health_directories: string
  support_groups: string
  support_groups_found_on: string
  source_tag: SourceTag
  confidence: TrustBand
  date_added: string
  created_at: string
  updated_at: string
  run_id: number | null
  geo_id: number | null
  // USER-owned outreach fields (ADR-022)
  outreach_status: OutreachStatus
  outreach_notes: string
  contacted_at: string | null
  outreach_updated_at: string | null
  outreach_updated_by: string | null
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

export interface AuthUser {
  username: string
  name: string
}

export interface Stats {
  total_prospects: number
  high_trust: number
  with_email: number
  geos_covered: number
  outreach: Record<OutreachStatus, number>
  last_run: Run | null
}
