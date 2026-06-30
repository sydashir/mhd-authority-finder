import { useState } from 'react'
import { ApiError } from './api/client'
import { useProspects } from './api/hooks'
import type { Prospect } from './api/types'
import { FilterBar, type ProspectQueryFilters } from './components/FilterBar'
import { Header } from './components/Header'
import { Pagination } from './components/Pagination'
import { ProspectsTable } from './components/ProspectsTable'
import { EmptyState, ErrorState, TableSkeleton } from './components/states'

const PAGE_SIZE = 50

function App() {
  const [filters, setFilters] = useState<ProspectQueryFilters>({})
  const [offset, setOffset] = useState(0)
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

  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="flex flex-1 flex-col overflow-hidden p-5">
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
          <FilterBar
            filters={filters}
            onChange={patchFilters}
            onReset={resetFilters}
            activeCount={activeCount}
          />
          <div
            className={`flex-1 overflow-auto transition-opacity ${
              query.isPlaceholderData ? 'opacity-60' : ''
            }`}
          >
            {query.isPending ? (
              <TableSkeleton />
            ) : query.isError ? (
              <ErrorState message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
            ) : query.data.items.length === 0 ? (
              <EmptyState />
            ) : (
              <ProspectsTable
                prospects={query.data.items}
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
  )
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return `The API returned ${error.status}.`
  return 'Couldn’t reach the API — is the backend running on the configured URL?'
}

export default App
