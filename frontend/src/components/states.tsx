import { AlertTriangle, SearchX } from 'lucide-react'

export function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 10 }, (_, i) => i).map((i) => (
        <div key={`sk-${i}`} className="h-7 animate-pulse rounded bg-raised" />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-12 text-center">
      <span className="text-fg-subtle">
        <AlertTriangle size={28} strokeWidth={1.5} />
      </span>
      <div className="text-[13px] font-medium text-fg">Couldn’t load prospects</div>
      <div className="max-w-md text-[12px] text-fg-subtle">{message}</div>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md border border-border bg-surface px-3 py-1.5 text-[12px] font-medium text-fg-muted hover:bg-raised"
      >
        Retry
      </button>
    </div>
  )
}

export function EmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-12 text-center text-fg-subtle">
      <SearchX size={28} strokeWidth={1.5} />
      <span className="text-[13px]">No prospects match these filters.</span>
    </div>
  )
}
