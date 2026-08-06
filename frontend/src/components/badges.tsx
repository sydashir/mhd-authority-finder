import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import type { OutreachStatus, RunStatus, SourceTag, TrustBand } from '../api/types'
import { OUTREACH_LABELS } from '../lib/format'

export function OutreachBadge({ status }: { status: OutreachStatus }) {
  return <span className={`badge badge-oc-${status}`}>{OUTREACH_LABELS[status]}</span>
}

export function TrustBadge({ band }: { band: TrustBand }) {
  return (
    <span className={`badge badge-${band}`}>
      <span className={`h-1.5 w-1.5 rounded-full dot-${band}`} aria-hidden />
      <span className="capitalize">{band}</span>
    </span>
  )
}

const SOURCE_CLASS: Record<SourceTag, string> = {
  MHD: 'badge-mhd',
  AH: 'badge-ah',
  Both: 'badge-both',
}

export function SourceBadge({ source }: { source: SourceTag }) {
  return (
    <span className={`badge font-semibold ${SOURCE_CLASS[source]}`} title={
      source === 'Both'
        ? 'This geography is published by both directories, so the prospect serves both'
        : `Published only by ${source}`
    }>
      {source}
    </span>
  )
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  if (status === 'running')
    return (
      <span className="badge badge-medium">
        <Loader2 size={11} className="animate-spin" /> Running
      </span>
    )
  if (status === 'success')
    return (
      <span className="badge badge-high">
        <CheckCircle2 size={11} /> Success
      </span>
    )
  return (
    <span className="badge badge-flag">
      <XCircle size={11} /> Failed
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
