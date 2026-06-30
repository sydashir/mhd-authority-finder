import { useState } from 'react'
import { ApiError } from './api/client'
import { useProspects } from './api/hooks'
import type { Prospect } from './api/types'
import { Header } from './components/Header'
import { ProspectsTable } from './components/ProspectsTable'
import { EmptyState, ErrorState, TableSkeleton } from './components/states'

function App() {
  const [selected, setSelected] = useState<Prospect | null>(null)
  const query = useProspects({ limit: 200 })

  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="flex flex-1 flex-col overflow-hidden p-5">
        <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
          <div className="flex-1 overflow-auto">
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
          <footer className="flex shrink-0 items-center justify-between border-t border-zinc-200 bg-zinc-50/60 px-4 py-2 text-[12px] text-zinc-500">
            <span>
              {query.data ? (
                <>
                  <span className="tnum font-medium text-zinc-700">{query.data.total}</span> prospects
                </>
              ) : (
                '—'
              )}
            </span>
          </footer>
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
