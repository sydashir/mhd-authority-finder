import { useQueryClient } from '@tanstack/react-query'
import { History, LogOut, Moon, Settings, Sun, Target, type LucideIcon } from 'lucide-react'
import { postLogout } from '../api/client'
import { useHealth } from '../api/hooks'
import type { AuthUser } from '../api/types'
import type { Theme } from '../lib/theme'
import { Logo } from './Logo'

export type View = 'prospects' | 'runs'

function NavItem({
  icon: Icon,
  label,
  active = false,
  soon = false,
  onClick,
}: {
  icon: LucideIcon
  label: string
  active?: boolean
  soon?: boolean
  onClick?: () => void
}) {
  const base =
    'relative flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors duration-150'
  const state = active
    ? 'bg-brand-soft text-brand'
    : soon
      ? 'text-fg-subtle cursor-default'
      : 'text-fg-muted hover:bg-raised hover:text-fg cursor-pointer'
  const content = (
    <>
      {active && (
        <span
          aria-hidden
          className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-full bg-brand"
        />
      )}
      <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
      <span className="flex-1 text-left">{label}</span>
      {soon && (
        <span className="rounded bg-raised px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-fg-subtle">
          Soon
        </span>
      )}
    </>
  )
  if (soon) return <div className={`${base} ${state}`}>{content}</div>
  return (
    <button type="button" onClick={onClick} className={`${base} ${state}`}>
      {content}
    </button>
  )
}

function initials(user: AuthUser): string {
  const source = user.name || user.username
  return source.slice(0, 1).toUpperCase()
}

export function Sidebar({
  active,
  onNavigate,
  theme,
  onToggleTheme,
  user,
}: {
  active: View
  onNavigate: (view: View) => void
  theme: Theme
  onToggleTheme: () => void
  user: AuthUser
}) {
  const { data, isError, isLoading } = useHealth()
  const connected = !isError && data?.database === 'ok'
  const queryClient = useQueryClient()

  async function onLogout() {
    try {
      await postLogout()
    } finally {
      await queryClient.invalidateQueries({ queryKey: ['me'] }) // flips the gate to login
    }
  }

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
        <NavItem
          icon={Target}
          label="Prospects"
          active={active === 'prospects'}
          onClick={() => onNavigate('prospects')}
        />
        <NavItem
          icon={History}
          label="Runs"
          active={active === 'runs'}
          onClick={() => onNavigate('runs')}
        />
        <NavItem icon={Settings} label="Settings" soon />
      </nav>

      <div className="space-y-1 border-t border-border p-3">
        <div className="flex items-center gap-2.5 rounded-md px-1.5 py-1.5">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand/15 text-[12px] font-semibold text-brand">
            {initials(user)}
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[12px] font-medium text-fg">
              {user.name || user.username}
            </div>
            <div className="truncate text-[11px] text-fg-subtle">Signed in</div>
          </div>
          <button
            type="button"
            onClick={onLogout}
            title="Sign out"
            aria-label="Sign out"
            className="shrink-0 rounded p-1 text-fg-subtle hover:bg-raised hover:text-fg"
          >
            <LogOut size={15} />
          </button>
        </div>

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
          className="flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium text-fg-muted transition-colors duration-150 hover:bg-raised hover:text-fg"
        >
          {theme === 'dark' ? (
            <Sun size={16} strokeWidth={1.8} />
          ) : (
            <Moon size={16} strokeWidth={1.8} />
          )}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  )
}
