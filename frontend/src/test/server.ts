// MSW server + realistic API fixtures. Tests exercise real component/hook logic against
// these shapes (not stubbed hooks), and override per-test with server.use(...).

import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import type { AuthUser, Prospect, Run, Stats } from '../api/types'

export const API = 'http://localhost:8000' // matches the client's default VITE_API_URL

export const authUser: AuthUser = {
  username: 'admin',
  name: 'admin',
}

export function makeProspect(over: Partial<Prospect> = {}): Prospect {
  const base: Prospect = {
    id: 1,
    website: 'ochealthinfo.gov',
    specific_page: 'https://ochealthinfo.gov/behavioral-health',
    email: 'bh@ochealthinfo.gov',
    phone: '+17148341234',
    contact_source: 'mailto (same-domain)',
    contact_trust: 'high',
    organization_description: 'County behavioral health',
    geo_served: 'Orange County, California',
    population: 3_165_820,
    competitor_links: '—',
    addiction_directories: '—',
    mental_health_directories: '—',
    support_groups: '—',
    support_groups_found_on: '',
    contact_found_on: '',
    domain_rating: null,
    source_tag: 'MHD',
    confidence: 'high',
    date_added: '2026-06-30',
    created_at: '2026-06-30T00:00:00Z',
    updated_at: '2026-06-30T00:00:00Z',
    run_id: 8,
    geo_id: 1,
    outreach_status: 'not_contacted',
    outreach_notes: '',
    contacted_at: null,
    outreach_updated_at: null,
    outreach_updated_by: null,
  }
  return { ...base, ...over }
}

export function makeRun(over: Partial<Run> = {}): Run {
  return {
    id: 8,
    site: 'both',
    status: 'success',
    started_at: '2026-07-06T00:00:00Z',
    finished_at: '2026-07-06T02:00:00Z',
    geos_processed: 72,
    rows_written: 622,
    billed_searches: 223,
    error_summary: null,
    ...over,
  }
}

export const stats: Stats = {
  total_prospects: 622,
  high_trust: 77,
  with_email: 386,
  geos_covered: 72,
  outreach: {
    not_contacted: 622,
    contacted: 0,
    responded: 0,
    interested: 0,
    not_interested: 0,
    linked: 0,
    bounced: 0,
  },
  last_run: makeRun(),
}

const DEFAULT_PROSPECTS = [
  makeProspect({ id: 1, website: 'a.gov', contact_trust: 'high', source_tag: 'MHD' }),
  makeProspect({ id: 2, website: 'b.edu', contact_trust: 'low', source_tag: 'AH', email: '' }),
]

// Default happy-path handlers. Auth is "signed in" by default so app-shell tests render;
// auth tests override /auth/me to 401/403.
export const handlers = [
  http.get(`${API}/health`, () => HttpResponse.json({ status: 'ok', database: 'ok' })),
  http.get(`${API}/auth/me`, () => HttpResponse.json(authUser)),
  http.post(`${API}/auth/logout`, () => HttpResponse.json({ ok: true })),
  http.get(`${API}/stats`, () => HttpResponse.json(stats)),
  http.get(`${API}/prospects`, ({ request }) => {
    const url = new URL(request.url)
    let items = DEFAULT_PROSPECTS
    const trust = url.searchParams.get('contact_trust')
    const source = url.searchParams.get('source_tag')
    if (trust) items = items.filter((p) => p.contact_trust === trust)
    if (source) items = items.filter((p) => p.source_tag === source)
    return HttpResponse.json({ items, total: items.length, limit: 50, offset: 0 })
  }),
  http.get(`${API}/runs`, () =>
    HttpResponse.json({ items: [makeRun()], total: 1, limit: 50, offset: 0 }),
  ),
  http.post(`${API}/runs`, () => HttpResponse.json({ run_id: 9, status: 'running' })),
]

export const server = setupServer(...handlers)
