import type { SourceTag, TrustBand } from '../api/types'

export function TrustBadge({ band }: { band: TrustBand }) {
  return (
    <span className={`badge badge-${band}`}>
      <span className={`h-1.5 w-1.5 rounded-full dot-${band}`} aria-hidden />
      <span className="capitalize">{band}</span>
    </span>
  )
}

export function SourceBadge({ source }: { source: SourceTag }) {
  return (
    <span className={`badge font-semibold ${source === 'MHD' ? 'badge-mhd' : 'badge-ah'}`}>
      {source}
    </span>
  )
}

/** Confidence is secondary to Contact Trust — rendered lighter (dot + label). */
export function ConfidenceTag({ band }: { band: TrustBand }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] capitalize text-fg-muted">
      <span className={`h-1.5 w-1.5 rounded-full dot-${band}`} aria-hidden />
      {band}
    </span>
  )
}
