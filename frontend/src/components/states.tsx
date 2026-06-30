export function TableSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 10 }, (_, i) => i).map((i) => (
        <div key={`sk-${i}`} className="h-7 animate-pulse rounded bg-zinc-100" />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-12 text-center">
      <div className="text-[13px] font-medium text-zinc-700">Couldn’t load prospects</div>
      <div className="max-w-md text-[12px] text-zinc-400">{message}</div>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-[12px] font-medium text-zinc-600 hover:bg-zinc-50"
      >
        Retry
      </button>
    </div>
  )
}

export function EmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center p-12 text-[13px] text-zinc-400">
      No prospects match these filters.
    </div>
  )
}
