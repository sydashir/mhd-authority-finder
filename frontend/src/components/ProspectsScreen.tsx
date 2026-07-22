import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { useProspects } from '../api/hooks'
import type { Prospect } from '../api/types'
import { ExportActions } from './ExportActions'
import { FilterBar, type ProspectQueryFilters } from './FilterBar'
import { Pagination } from './Pagination'
import { ProspectDrawer } from './ProspectDrawer'
import { ProspectsTable } from './ProspectsTable'
import { StatCards } from './StatCards'
import { Topbar } from './Topbar'
import type { ToastData } from './Toast'
import { EmptyState, ErrorState, TableSkeleton } from './states'

const PAGE_SIZE = 50

export function ProspectsScreen({ notify }: { notify: (toast: ToastData) => void }) {
  const [filters, setFilters] = useState<ProspectQueryFilters>({})
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Prospect | null>(null)

  // Debounce the search box, then query the API — searching the WHOLE dataset, not just the
  // loaded page (ADR-025). A stale-page match no longer falsely reports "no prospects".
  const debouncedSearch = useDebounced(search, 300)
  useEffect(() => setOffset(0), [debouncedSearch]) // a new search returns to the first page

  const query = useProspects({
    ...filters,
    search: debouncedSearch.trim() || undefined,
    limit: PAGE_SIZE,
    offset,
  })
  const activeCount = Object.values(filters).filter(Boolean).length

  function patchFilters(patch: Partial<ProspectQueryFilters>) {
    setFilters((f) => ({ ...f, ...patch }))
    setOffset(0) // any filter change returns to the first page
  }

  function resetFilters() {
    setFilters({})
    setOffset(0)
  }

  const visible = query.data?.items ?? []

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <Topbar
        title="Prospects"
        subtitle={query.data ? `${query.data.total} total` : undefined}
        search={search}
        onSearch={setSearch}
        actions={<ExportActions filters={filters} notify={notify} />}
      />
      <main className="flex flex-1 flex-col gap-5 overflow-hidden p-6">
        <StatCards />
        <div
          className={`card flex flex-1 flex-col overflow-hidden transition-opacity ${
            query.isPlaceholderData ? 'opacity-60' : ''
          }`}
        >
          <FilterBar
            filters={filters}
            onChange={patchFilters}
            onReset={resetFilters}
            activeCount={activeCount}
          />
          <div className="flex flex-1 flex-col overflow-hidden">
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
      <ProspectDrawer prospect={selected} onClose={() => setSelected(null)} notify={notify} />
    </div>
  )
}

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(id)
  }, [value, delayMs])
  return debounced
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `The API returned ${error.status}.`
  return 'Couldn’t reach the API — is the backend running on the configured URL?'
}
