import { useState } from 'react'
import { ApiError } from './api/client'
import { useProspects } from './api/hooks'
import type { Prospect } from './api/types'
import { FilterBar, type ProspectQueryFilters } from './components/FilterBar'
import { Pagination } from './components/Pagination'
import { ProspectDrawer } from './components/ProspectDrawer'
import { ProspectsTable } from './components/ProspectsTable'
import { Sidebar } from './components/Sidebar'
import { Topbar } from './components/Topbar'
import { EmptyState, ErrorState, TableSkeleton } from './components/states'
import { useTheme } from './lib/theme'

const PAGE_SIZE = 50

function App() {
  const { theme, toggle } = useTheme()
  const [filters, setFilters] = useState<ProspectQueryFilters>({})
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Prospect | null>(null)

  const query = useProspects({ ...filters, limit: PAGE_SIZE, offset })
  const activeCount = Object.values(filters).filter(Boolean).length

  function patchFilters(patch: Partial<ProspectQueryFilters>) {
    setFilters((f) => ({ ...f, ...patch }))
    setOffset(0) // any filter change returns to the first page
  }

  function resetFilters() {
    setFilters({})
    setOffset(0)
  }

  const items = query.data?.items ?? []
  const q = search.trim().toLowerCase()
  const visible = q
    ? items.filter((p) => `${p.website} ${p.email} ${p.geo_served}`.toLowerCase().includes(q))
    : items

  return (
    <div className="flex h-full">
      <Sidebar theme={theme} onToggleTheme={toggle} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          title="Prospects"
          subtitle={query.data ? `${query.data.total} total` : undefined}
          search={search}
          onSearch={setSearch}
        />
        <main className="flex flex-1 flex-col gap-5 overflow-hidden p-6">
          <div
            className={`flex flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-sm transition-opacity ${
              query.isPlaceholderData ? 'opacity-60' : ''
            }`}
          >
            <FilterBar
              filters={filters}
              onChange={patchFilters}
              onReset={resetFilters}
              activeCount={activeCount}
            />
            <div className="flex-1 overflow-auto">
              {query.isPending ? (
                <TableSkeleton />
              ) : query.isError ? (
                <ErrorState message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
              ) : visible.length === 0 ? (
                <EmptyState />
              ) : (
                <ProspectsTable
                  prospects={visible}
                  selectedId={selected?.id ?? null}
                  onSelect={setSelected}
                />
              )}
            </div>
            <Pagination
              total={query.data?.total ?? 0}
              limit={PAGE_SIZE}
              offset={offset}
              onOffsetChange={setOffset}
            />
          </div>
        </main>
      </div>
      <ProspectDrawer prospect={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `The API returned ${error.status}.`
  return 'Couldn’t reach the API — is the backend running on the configured URL?'
}

export default App
