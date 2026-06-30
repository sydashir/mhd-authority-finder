import type { SourceTag, TrustBand } from '../api/types'

const TRUST_STYLES: Record<TrustBand, string> = {
  high: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  medium: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  low: 'bg-zinc-100 text-zinc-500 ring-zinc-500/20',
}

const TRUST_DOT: Record<TrustBand, string> = {
  high: 'bg-emerald-500',
  medium: 'bg-amber-500',
  low: 'bg-zinc-400',
}

const SOURCE_STYLES: Record<SourceTag, string> = {
  MHD: 'bg-indigo-50 text-indigo-700 ring-indigo-600/20',
  AH: 'bg-sky-50 text-sky-700 ring-sky-600/20',
}

export function TrustBadge({ band }: { band: TrustBand }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium capitalize ring-1 ring-inset ${TRUST_STYLES[band]}`}
    >
      {band}
    </span>
  )
}

export function SourceBadge({ source }: { source: SourceTag }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${SOURCE_STYLES[source]}`}
    >
      {source}
    </span>
  )
}

/** Confidence is secondary to Contact Trust, so render it lighter: a dot + label. */
export function ConfidenceTag({ band }: { band: TrustBand }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] capitalize text-zinc-500">
      <span className={`h-1.5 w-1.5 rounded-full ${TRUST_DOT[band]}`} aria-hidden />
      {band}
    </span>
  )
}
