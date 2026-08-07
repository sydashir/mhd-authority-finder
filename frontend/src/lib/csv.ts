import type { Prospect } from '../api/types'

// Mirrors the backend OUTPUT_HEADER (the deliverable column order). Kept in step by
// csv.test.ts, which fails when a deliverable field on Prospect is missing here — this list
// silently lagged Domain Rating by several releases, so the client's CSV export was short a
// column nobody noticed.
export const HEADER = [
  'Website',
  'Specific Page',
  'Email',
  'Phone',
  'Contact Source',
  'Contact Trust',
  'Organization Description',
  'Geo Served',
  'Population',
  'Competitor Links',
  'Source Tag',
  'Date Added',
  'Confidence',
  'Domain Rating',
  'Contact Found On',
  'Addiction Directories',
  'Mental Health Directories',
  'Support Groups',
  'Support Groups Found On',
]

function cell(value: string | number | null): string {
  const s = value === null ? '' : String(value)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function row(p: Prospect): string {
  return [
    p.website,
    p.specific_page,
    p.email,
    p.phone,
    p.contact_source,
    p.contact_trust,
    p.organization_description,
    p.geo_served,
    p.population,
    p.competitor_links,
    p.source_tag,
    p.date_added,
    p.confidence,
    p.domain_rating,
    p.contact_found_on,
    p.addiction_directories,
    p.mental_health_directories,
    p.support_groups,
    p.support_groups_found_on,
  ]
    .map(cell)
    .join(',')
}

export function prospectsToCsv(rows: Prospect[]): string {
  return [HEADER.join(','), ...rows.map(row)].join('\n')
}

export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
