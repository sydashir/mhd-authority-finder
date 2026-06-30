export function Pagination({
  total,
  limit,
  offset,
  onOffsetChange,
}: {
  total: number
  limit: number
  offset: number
  onOffsetChange: (offset: number) => void
}) {
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + limit, total)
  const canPrev = offset > 0
  const canNext = to < total

  const btn =
    'rounded-md border border-zinc-200 bg-white px-2.5 py-1 text-[12px] font-medium text-zinc-600 enabled:hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-40'

  return (
    <div className="flex shrink-0 items-center justify-between border-t border-zinc-200 bg-zinc-50/60 px-4 py-2 text-[12px] text-zinc-500">
      <span>
        Showing <span className="tnum font-medium text-zinc-700">{from}</span>–
        <span className="tnum font-medium text-zinc-700">{to}</span> of{' '}
        <span className="tnum font-medium text-zinc-700">{total}</span>
      </span>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          className={btn}
          disabled={!canPrev}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          Prev
        </button>
        <button
          type="button"
          className={btn}
          disabled={!canNext}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  )
}
