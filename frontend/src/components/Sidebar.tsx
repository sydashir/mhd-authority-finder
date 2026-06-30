import { History, Moon, Settings, Sun, Target, type LucideIcon } from 'lucide-react'
import { useHealth } from '../api/hooks'
import type { Theme } from '../lib/theme'
import { Logo } from './Logo'

function NavItem({
  icon: Icon,
  label,
  active = false,
  soon = false,
}: {
  icon: LucideIcon
  label: string
  active?: boolean
  soon?: boolean
}) {
  const base = 'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium'
  const state = active
    ? 'bg-brand/10 text-brand'
    : soon
      ? 'text-fg-subtle cursor-default'
      : 'text-fg-muted hover:bg-raised hover:text-fg cursor-pointer'
  return (
    <div className={`${base} ${state}`}>
      <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
      <span className="flex-1">{label}</span>
      {soon && (
        <span className="rounded bg-raised px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-fg-subtle">
          Soon
        </span>
      )}
    </div>
  )
}

export function Sidebar({ theme, onToggleTheme }: { theme: Theme; onToggleTheme: () => void }) {
  const { data, isError, isLoading } = useHealth()
  const connected = !isError && data?.database === 'ok'

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-4">
        <span className="text-brand">
          <Logo size={22} />
        </span>
        <span className="text-[15px] font-semibold tracking-tight">AuthorityScout</span>
      </div>

      <nav className="flex-1 space-y-0.5 p-3">
        <div className="px-2.5 pb-1.5 pt-1 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
          Workspace
        </div>
        <NavItem icon={Target} label="Prospects" active />
        <NavItem icon={History} label="Runs" soon />
        <NavItem icon={Settings} label="Settings" soon />
      </nav>

      <div className="space-y-1 border-t border-border p-3">
        <div className="flex items-center gap-2 px-2.5 py-1 text-[11px] text-fg-subtle">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              isLoading ? 'animate-pulse bg-amber-400' : connected ? 'bg-emerald-500' : 'bg-red-500'
            }`}
          />
          {isLoading ? 'Connecting…' : connected ? 'API connected' : 'API offline'}
        </div>
        <button
          type="button"
          onClick={onToggleTheme}
          className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium text-fg-muted hover:bg-raised hover:text-fg"
        >
          {theme === 'dark' ? <Sun size={16} strokeWidth={1.8} /> : <Moon size={16} strokeWidth={1.8} />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  )
}
