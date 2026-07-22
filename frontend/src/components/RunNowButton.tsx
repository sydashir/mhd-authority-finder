import { AlertTriangle, Loader2, Play } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { useTriggerRun } from '../api/hooks'
import type { RunMode, RunSite } from '../api/types'
import type { ToastData } from './Toast'

const SITES: { value: RunSite; label: string }[] = [
  { value: 'both', label: 'Both' },
  { value: 'mhd', label: 'MHD' },
  { value: 'ah', label: 'AH' },
]

const MODES: { value: RunMode; label: string; hint: string }[] = [
  {
    value: 'incremental',
    label: 'New geos only',
    hint: 'Cost-safe — spends nothing if nothing is new.',
  },
  {
    value: 'full',
    label: 'Full re-scan',
    hint: 'Re-scans every known geo — may use search credits.',
  },
]

export function RunNowButton({
  notify,
  disabled = false,
}: {
  notify: (toast: ToastData) => void
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [site, setSite] = useState<RunSite>('both')
  const [mode, setMode] = useState<RunMode>('incremental')
  const ref = useRef<HTMLDivElement>(null)
  const trigger = useTriggerRun()

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onDown)
    return () => window.removeEventListener('mousedown', onDown)
  }, [open])

  async function start() {
    try {
      const res = await trigger.mutateAsync({ site, mode })
      notify({ message: `Run #${res.run_id} started — ${site}, ${mode}.`, tone: 'success' })
      setOpen(false)
    } catch (err) {
      // 409 = a run is already in progress or the daily budget is spent — surface it verbatim.
      const message =
        err instanceof ApiError && err.status === 409
          ? err.message
          : 'Couldn’t start the run — is the backend running?'
      notify({ message, tone: 'error' })
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        className="inline-flex items-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-[12px] font-semibold text-brand-fg hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-60"
      >
        {disabled ? (
          <>
            <Loader2 size={13} className="animate-spin" /> Run in progress
          </>
        ) : (
          <>
            <Play size={13} strokeWidth={2.2} /> Run now
          </>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-1.5 w-72 rounded-xl border border-border bg-surface p-3 shadow-2xl">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-fg-subtle">
            Site
          </div>
          <div className="flex gap-1 rounded-lg border border-border bg-app p-0.5">
            {SITES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => setSite(s.value)}
                className={`flex-1 rounded-md px-2 py-1 text-[12px] font-medium ${
                  site === s.value ? 'bg-brand text-brand-fg' : 'text-fg-muted hover:text-fg'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="mb-1.5 mt-3 text-[10px] font-semibold uppercase tracking-wide text-fg-subtle">
            Mode
          </div>
          <div className="space-y-1.5">
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => setMode(m.value)}
                className={`w-full rounded-lg border px-2.5 py-2 text-left ${
                  mode === m.value ? 'border-brand/50 bg-brand/10' : 'border-border hover:bg-raised'
                }`}
              >
                <div className="flex items-center gap-2 text-[12px] font-medium text-fg">
                  <span
                    className={`h-2.5 w-2.5 rounded-full border ${
                      mode === m.value ? 'border-brand bg-brand' : 'border-border-strong'
                    }`}
                  />
                  {m.label}
                </div>
                <div className="mt-0.5 pl-5 text-[11px] text-fg-subtle">{m.hint}</div>
              </button>
            ))}
          </div>

          {mode === 'full' && (
            <div className="mt-2 flex items-start gap-1.5 rounded-md bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-700 dark:text-amber-300">
              <AlertTriangle size={13} className="mt-px shrink-0" />A full re-scan can spend SerpAPI
              search credits.
            </div>
          )}

          <button
            type="button"
            onClick={start}
            disabled={trigger.isPending}
            className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-[12px] font-semibold text-brand-fg hover:bg-brand-strong disabled:opacity-60"
          >
            {trigger.isPending ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <Play size={13} />
            )}
            Start run
          </button>
        </div>
      )}
    </div>
  )
}
