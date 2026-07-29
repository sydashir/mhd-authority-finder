// oxlint-disable react/only-export-components -- test helper file, not an HMR boundary
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { ApiError } from '../api/client'

/** A QueryClient mirroring main.tsx's 401→re-auth cache handler, with retries off for tests. */
export function makeClient(): QueryClient {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (error instanceof ApiError && error.status === 401 && query.queryKey[0] !== 'me') {
          void client.invalidateQueries({ queryKey: ['me'] })
        }
      },
    }),
  })
  return client
}

function Providers({ client, children }: { client: QueryClient; children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

export function renderWithProviders(
  ui: ReactElement,
  client: QueryClient = makeClient(),
): RenderResult & { client: QueryClient } {
  const result = render(<Providers client={client}>{ui}</Providers>)
  return { ...result, client }
}
