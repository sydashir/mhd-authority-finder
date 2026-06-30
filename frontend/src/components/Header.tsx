import { useHealth } from '../api/hooks'

export function Header() {
  const { data, isError, isLoading } = useHealth()
  const connected = !isError && data?.database === 'ok'
  const label = isLoading ? 'Connecting…' : connected ? 'Backend connected' : 'Backend offline'
  const dot = isLoading ? 'bg-amber-400' : connected ? 'bg-emerald-500' : 'bg-red-500'

  return (
    <header className="sticky top-0 z-30 flex h-12 shrink-0 items-center justify-between border-b border-zinc-200 bg-white px-5">
      <div className="flex items-baseline gap-2.5">
        <span className="text-[14px] font-semibold tracking-tight text-zinc-900">
          MHD Authority Finder
        </span>
        <span className="hidden text-[12px] text-zinc-400 sm:inline">Outreach prospects</span>
      </div>
      <div className="flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-1">
        <span
          className={`h-1.5 w-1.5 rounded-full ${dot} ${isLoading ? 'animate-pulse' : ''}`}
          aria-hidden
        />
        <span className="text-[11px] font-medium text-zinc-500">{label}</span>
      </div>
    </header>
  )
}
