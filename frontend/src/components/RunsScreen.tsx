import { useQueryClient } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { ApiError } from '../api/client'
import { useRuns } from '../api/hooks'
import type { Run } from '../api/types'
import { duration, timeAgo } from '../lib/format'
import { RunStatusBadge } from './badges'
import { RunNowButton } from './RunNowButton'
import { Topbar } from './Topbar'
import type { ToastData } from './Toast'

const TH =
  'sticky top-0 z-10 border-b border-border bg-raised px-4 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-fg-subtle whitespace-nowrap'
const TD = 'border-b border-border px-4 py-2.5 align-middle text-[13px]'

function SiteTag({ site }: { site: string }) {
  return (
    <span className="badge bg-raised font-semibold text-fg-muted">
      {site === 'both' ? 'Both' : site.toUpperCase()}
    </span>
  )
}

function num(n: number, muted = false): string {
  return muted && n === 0 ? '—' : n.toLocaleString()
}

function RunsTable({ runs }: { runs: Run[] }) {
  return (
    <table className="w-full border-separate border-spacing-0">
      <thead>
        <tr>
          <th className={TH}>Site</th>
          <th className={TH}>Status</th>
          <th className={TH}>Started</th>
          <th className={TH}>Duration</th>
          <th className={`${TH} text-right`}>Geos</th>
          <th className={`${TH} text-right`}>Rows added</th>
          <th className={`${TH} text-right`}>Billed</th>
          <th className={TH}>Notes</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => {
          const dur = duration(r.started_at, r.finished_at)
          return (
            <tr key={r.id} className="hover:bg-raised/50">
              <td className={TD}>
                <SiteTag site={r.site} />
              </td>
              <td className={TD}>
                <RunStatusBadge status={r.status} />
              </td>
              <td className={`${TD} text-fg-muted`} title={new Date(r.started_at).toLocaleString()}>
                {timeAgo(r.started_at)}
              </td>
              <td className={`${TD} tnum text-fg-muted`}>{dur ?? (r.status === 'running' ? '…' : '—')}</td>
              <td className={`${TD} tnum text-right text-fg`}>{num(r.geos_processed)}</td>
              <td className={`${TD} tnum text-right text-fg`}>{num(r.rows_written)}</td>
              <td
                className={`${TD} tnum text-right ${r.billed_searches > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-fg-subtle'}`}
              >
                {num(r.billed_searches, true)}
              </td>
              <td className={`${TD} max-w-[280px]`}>
                {r.error_summary ? (
                  <span className="truncate text-[12px] text-rose-600 dark:text-rose-400" title={r.error_summary}>
                    {r.error_summary}
                  </span>
                ) : (
                  <span className="text-fg-subtle/50">—</span>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function RunsSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 6 }, (_, i) => i).map((i) => (
        <div key={`run-sk-${i}`} className="h-8 animate-pulse rounded bg-raised" />
      ))}
    </div>
  )
}

export function RunsScreen({ notify }: { notify: (toast: ToastData) => void }) {
  const queryClient = useQueryClient()
  const runs = useRuns()

  // Post-run refresh: when a previously-running run turns terminal, refresh the
  // dashboard's prospects + stats so new rows / Last Run appear automatically.
  const runningIds = useRef<Set<number>>(new Set())
  useEffect(() => {
    const items = runs.data?.items ?? []
    const current = new Set(items.filter((r) => r.status === 'running').map((r) => r.id))
    let finished = false
    for (const id of runningIds.current) if (!current.has(id)) finished = true
    runningIds.current = current
    if (finished) {
      void queryClient.invalidateQueries({ queryKey: ['prospects'] })
      void queryClient.invalidateQueries({ queryKey: ['stats'] })
    }
  }, [runs.data, queryClient])

  const items = runs.data?.items ?? []

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <Topbar
        title="Runs"
        subtitle={runs.data ? `${runs.data.total} total` : undefined}
        actions={<RunNowButton notify={notify} />}
      />
      <main className="flex flex-1 flex-col overflow-hidden p-6">
        <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
          <div className="flex flex-1 flex-col overflow-auto">
            {runs.isPending ? (
              <RunsSkeleton />
            ) : runs.isError ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center text-fg-subtle">
                <History size={28} strokeWidth={1.5} />
                <div className="text-[13px] font-medium text-fg">Couldn’t load runs</div>
                <div className="text-[12px]">
                  {runs.error instanceof ApiError
                    ? `The API returned ${runs.error.status}.`
                    : 'Is the backend running?'}
                </div>
                <button
                  type="button"
                  onClick={() => void runs.refetch()}
                  className="mt-1 rounded-md border border-border bg-surface px-3 py-1.5 text-[12px] font-medium text-fg-muted hover:bg-raised"
                >
                  Retry
                </button>
              </div>
            ) : items.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center text-fg-subtle">
                <History size={28} strokeWidth={1.5} />
                <div className="text-[13px]">No runs yet — start one with “Run now”.</div>
              </div>
            ) : (
              <RunsTable runs={items} />
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
