import { History, Mail, MapPin, Send, ShieldCheck, Target, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useStats } from '../api/hooks'
import type { RunStatus } from '../api/types'
import { formatDate } from '../lib/format'

function pct(n: number, d: number): number {
  return d === 0 ? 0 : Math.round((n / d) * 100)
}

function Card({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: LucideIcon
  label: string
  value: ReactNode
  detail: ReactNode
}) {
  return (
    <div className="card card-interactive p-4">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">
          {label}
        </span>
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-soft text-brand">
          <Icon size={15} strokeWidth={2} />
        </span>
      </div>
      <div className="mt-3 text-[26px] font-semibold leading-none tracking-tight text-fg tnum">
        {value}
      </div>
      <div className="mt-1.5 text-[12px] text-fg-subtle">{detail}</div>
    </div>
  )
}

const RUN_DOT: Record<RunStatus, string> = {
  success: 'bg-emerald-500',
  failed: 'bg-red-500',
  running: 'bg-amber-500',
}

export function StatCards() {
  const { data, isPending } = useStats()

  if (isPending || !data) {
    return (
      <div className="grid shrink-0 grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => i).map((i) => (
          <div key={`stat-sk-${i}`} className="h-[92px] animate-pulse rounded-xl bg-raised" />
        ))}
      </div>
    )
  }

  const emailPct = pct(data.with_email, data.total_prospects)
  const highPct = pct(data.high_trust, data.total_prospects)
  const run = data.last_run
  const worked = data.total_prospects - (data.outreach.not_contacted ?? 0)
  const responded = data.outreach.responded ?? 0

  return (
    <div className="grid shrink-0 grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
      <Card
        icon={Target}
        label="Total Prospects"
        value={data.total_prospects.toLocaleString()}
        detail={`across ${data.geos_covered} geos`}
      />
      <Card
        icon={ShieldCheck}
        label="High-Trust"
        value={data.high_trust.toLocaleString()}
        detail={`${highPct}% of prospects`}
      />
      <Card
        icon={Mail}
        label="With Email"
        value={`${emailPct}%`}
        detail={`${data.with_email} of ${data.total_prospects}`}
      />
      <Card
        icon={MapPin}
        label="Geos Covered"
        value={data.geos_covered.toLocaleString()}
        detail="states & localities"
      />
      <Card
        icon={Send}
        label="Outreach"
        value={worked.toLocaleString()}
        detail={`${responded} responded · ${data.outreach.not_contacted ?? 0} to go`}
      />
      <Card
        icon={History}
        label="Last Run"
        value={run ? formatDate(run.started_at) : '—'}
        detail={
          run ? (
            <span className="inline-flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 rounded-full ${RUN_DOT[run.status]}`} aria-hidden />
              {run.status} · {run.rows_written} rows
            </span>
          ) : (
            'no runs yet'
          )
        }
      />
    </div>
  )
}
