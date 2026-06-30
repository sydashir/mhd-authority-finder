// Pure display helpers for the table + drawer.

export function formatPopulation(p: number | null): string {
  return p === null ? '—' : p.toLocaleString('en-US')
}

/** The pipeline joins competitor domains with "; " (or "—" when none). */
export function competitorList(raw: string): string[] {
  const value = raw.trim()
  if (!value || value === '—') return []
  return value
    .split(';')
    .map((s) => s.trim())
    .filter(Boolean)
}

/** A specific page shown compactly as its path (the domain is its own column). */
export function pagePath(url: string): string {
  try {
    const u = new URL(url)
    const path = (u.pathname + u.search).replace(/\/$/, '')
    return path || '/'
  } catch {
    return url
  }
}

export function formatDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
}

/** Empty contact fields render as a muted dash, not blank. */
export function orDash(value: string): string {
  return value.trim() || '—'
}
