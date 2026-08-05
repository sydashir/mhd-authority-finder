import { describe, expect, it } from 'vitest'
import { makeProspect } from '../test/server'
import { HEADER, prospectsToCsv } from './csv'

// Fields on Prospect that are NOT part of the deliverable: DB bookkeeping and the team's
// own outreach workspace (ADR-022), which stays in the app rather than in an exported file.
const NOT_DELIVERABLE = new Set([
  'id',
  'created_at',
  'updated_at',
  'run_id',
  'geo_id',
  'outreach_status',
  'outreach_notes',
  'contacted_at',
  'outreach_updated_at',
  'outreach_updated_by',
])

describe('prospectsToCsv', () => {
  it('exports every deliverable field on Prospect', () => {
    // Structural, not a snapshot: adding a column to the deliverable and forgetting the CSV
    // is how Domain Rating went missing from the client's export without a single failure.
    const deliverable = Object.keys(makeProspect({})).filter((f) => !NOT_DELIVERABLE.has(f))
    expect(HEADER.length).toBe(deliverable.length)
  })

  it('has one header column per emitted value', () => {
    // Comma-free values so a naive split is a valid count; quoting has its own test below.
    const csv = prospectsToCsv([
      makeProspect({ geo_served: 'California', organization_description: 'plain' }),
    ])
    const [header, row] = csv.split('\n')
    expect(header.split(',').length).toBe(HEADER.length)
    expect(row.split(',').length).toBe(HEADER.length)
  })

  it('carries the columns that previously went missing', () => {
    const csv = prospectsToCsv([
      makeProspect({
        domain_rating: 34,
        contact_found_on: 'https://county.gov/resources',
      }),
    ])
    expect(csv).toContain('Domain Rating')
    expect(csv).toContain('Contact Found On')
    expect(csv).toContain('34')
    expect(csv).toContain('https://county.gov/resources')
  })

  it('quotes a value containing a comma so columns do not shift', () => {
    const csv = prospectsToCsv([makeProspect({ competitor_links: 'a.com; b.com, c.com' })])
    expect(csv).toContain('"a.com; b.com, c.com"')
  })
})
