import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as Sentry from '@sentry/react'
import { ApiError } from './api/client'
import { ErrorFallback } from './components/ErrorFallback'
import { initMonitoring } from './lib/monitoring'
import './index.css'
import App from './App.tsx'

initMonitoring() // no-op unless VITE_SENTRY_DSN is set (silent in dev)

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
  // A 401 from a DATA call means the session is gone -> re-check auth (flips to Login).
  // Skip the ['me'] query itself, or its own 401 would loop forever.
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (error instanceof ApiError && error.status === 401 && query.queryKey[0] !== 'me') {
        void queryClient.invalidateQueries({ queryKey: ['me'] })
      }
    },
  }),
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* A component crash shows a calm recovery screen (and reports to Sentry), never a white page. */}
    <Sentry.ErrorBoundary fallback={({ resetError }) => <ErrorFallback resetError={resetError} />}>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </GoogleOAuthProvider>
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
