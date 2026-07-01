import { Search } from 'lucide-react'
import type { ReactNode } from 'react'

export function Topbar({
  title,
  subtitle,
  search,
  onSearch,
  actions,
}: {
  title: string
  subtitle?: string
  search?: string
  onSearch?: (value: string) => void
  actions?: ReactNode
}) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-surface px-6">
      <div className="flex items-baseline gap-2.5">
        <h1 className="text-[15px] font-semibold tracking-tight">{title}</h1>
        {subtitle && <span className="text-[12px] text-fg-subtle">{subtitle}</span>}
      </div>

      {onSearch && (
        <div className="relative ml-auto w-64">
          <Search
            size={14}
            className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-subtle"
          />
          <input
            type="search"
            value={search ?? ''}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search domain or email…"
            className="w-full rounded-md border border-border bg-app py-1.5 pl-8 pr-3 text-[13px] text-fg outline-none placeholder:text-fg-subtle focus:border-brand focus:ring-2 focus:ring-brand/25"
          />
        </div>
      )}

      {actions && (
        <div className={`flex items-center gap-2 ${onSearch ? '' : 'ml-auto'}`}>{actions}</div>
      )}
    </header>
  )
}
