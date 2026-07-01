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

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return iso
  const secs = Math.round((Date.now() - then) / 1000)
  if (secs < 45) return 'just now'
  const mins = Math.round(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.round(hrs / 24)
  return days < 30 ? `${days}d ago` : formatDate(iso)
}

export function duration(startIso: string, endIso: string | null): string | null {
  if (!endIso) return null
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime()
  if (Number.isNaN(ms) || ms < 0) return null
  const s = Math.round(ms / 1000)
  return s < 60 ? `${s}s` : `${Math.round(s / 60)}m`
}

/** Empty contact fields render as a muted dash, not blank. */
export function orDash(value: string): string {
  return value.trim() || '—'
}
