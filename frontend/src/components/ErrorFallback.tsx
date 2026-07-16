import { AlertTriangle } from 'lucide-react'

/** Shown by the top-level ErrorBoundary when a component crashes — a calm recovery screen
 *  instead of a white page (ADR-023). The error is reported to Sentry when monitoring is on. */
export function ErrorFallback({ resetError }: { resetError: () => void }) {
  return (
    <div className="flex h-full items-center justify-center bg-app p-6">
      <div className="card elevate-pop w-full max-w-sm rounded-2xl p-8 text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-brand">
          <AlertTriangle size={24} strokeWidth={1.8} />
        </span>
        <h1 className="mt-4 text-[17px] font-semibold tracking-tight text-fg">
          Something went wrong
        </h1>
        <p className="mt-1.5 text-[13px] text-fg-muted">
          An unexpected error occurred. Reloading usually clears it.
        </p>
        <button
          type="button"
          onClick={resetError}
          className="mt-5 inline-flex cursor-pointer items-center gap-1.5 rounded-md bg-brand px-4 py-2 text-[13px] font-medium text-brand-fg transition-colors hover:bg-brand-strong"
        >
          Reload the app
        </button>
      </div>
    </div>
  )
}
