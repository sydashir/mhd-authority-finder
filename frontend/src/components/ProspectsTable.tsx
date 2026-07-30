import { ArrowUpDown, ChevronDown, ChevronUp, Columns3 } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Prospect } from '../api/types'
import { competitorList, formatPopulation, orDash, pagePath } from '../lib/format'
import { ConfidenceTag, OutreachBadge, SourceBadge, TrustBadge } from './badges'

export type ColKey =
  | 'website'
  | 'specific_page'
  | 'email'
  | 'phone'
  | 'contact_trust'
  | 'outreach_status'
  | 'geo_served'
  | 'source_tag'
  | 'competitors'
  | 'population'
  | 'domain_rating'
  | 'confidence'

export interface SortState {
  key: ColKey
  dir: 'asc' | 'desc'
}

interface Column {
  key: ColKey
  label: string
  sortable: boolean
  right?: boolean
  render: (p: Prospect) => ReactNode
}

function CompetitorCell({ raw }: { raw: string }) {
  const links = competitorList(raw)
  if (links.length === 0) return <span className="text-fg-subtle/50">—</span>
  return (
    <span title={links.join(', ')} className="badge badge-flag">
      <svg viewBox="0 0 16 16" className="h-3 w-3" fill="currentColor" aria-hidden>
        <path d="M3 1.5a.75.75 0 0 1 .75.75v.34l8.36 2.39a.5.5 0 0 1 0 .96L4.5 8.06v6.19a.75.75 0 0 1-1.5 0V2.25A.75.75 0 0 1 3 1.5Z" />
      </svg>
      {links.length}
    </span>
  )
}

const COLUMNS: Column[] = [
  {
    key: 'website',
    label: 'Website',
    sortable: true,
    render: (p) => (
      <div className="max-w-[180px] truncate" title={p.website}>
        {p.website}
      </div>
    ),
  },
  {
    key: 'specific_page',
    label: 'Specific Page',
    sortable: false,
    render: (p) => (
      <a
        href={p.specific_page}
        target="_blank"
        rel="noreferrer"
        onClick={(e) => e.stopPropagation()}
        title={p.specific_page}
        className="block max-w-[230px] truncate text-brand hover:underline"
      >
        {pagePath(p.specific_page)}
      </a>
    ),
  },
  {
    key: 'email',
    label: 'Email',
    sortable: true,
    render: (p) => (
      <div className="max-w-[200px] truncate text-fg-muted" title={p.email}>
        {orDash(p.email)}
      </div>
    ),
  },
  {
    key: 'phone',
    label: 'Phone',
    sortable: false,
    render: (p) => <span className="tnum whitespace-nowrap text-fg-muted">{orDash(p.phone)}</span>,
  },
  {
    key: 'contact_trust',
    label: 'Trust',
    sortable: true,
    render: (p) => <TrustBadge band={p.contact_trust} />,
  },
  {
    key: 'outreach_status',
    label: 'Outreach',
    sortable: true,
    render: (p) => <OutreachBadge status={p.outreach_status} />,
  },
  {
    key: 'geo_served',
    label: 'Geo Served',
    sortable: true,
    render: (p) => (
      <div className="max-w-[170px] truncate text-fg-muted" title={p.geo_served}>
        {p.geo_served}
      </div>
    ),
  },
  {
    key: 'source_tag',
    label: 'Source',
    sortable: true,
    render: (p) => <SourceBadge source={p.source_tag} />,
  },
  {
    key: 'competitors',
    label: 'Competitors',
    sortable: true,
    render: (p) => <CompetitorCell raw={p.competitor_links} />,
  },
  {
    key: 'population',
    label: 'Population',
    sortable: true,
    right: true,
    render: (p) => (
      <span className="tnum whitespace-nowrap text-fg">{formatPopulation(p.population)}</span>
    ),
  },
  {
    key: 'domain_rating',
    label: 'DR',
    sortable: true,
    right: true,
    render: (p) => (
      // Blank, never 0: .gov/.edu are deliberately unscored, and 0 would read as
      // "no authority" rather than "not measured" (ADR-027).
      <span className="tnum whitespace-nowrap text-fg">
        {p.domain_rating === null ? (
          <span className="text-fg-subtle">—</span>
        ) : (
          Math.round(p.domain_rating)
        )}
      </span>
    ),
  },
  {
    key: 'confidence',
    label: 'Confidence',
    sortable: true,
    render: (p) => <ConfidenceTag band={p.confidence} />,
  },
]

const TH =
  'sticky top-0 z-10 border-b border-border bg-raised px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-fg-subtle whitespace-nowrap'
const TD =
  'border-b border-border px-3 py-1.5 align-middle transition-colors duration-100 group-hover:bg-raised/50'

function ColumnsMenu({
  hidden,
  onToggle,
}: {
  hidden: Set<ColKey>
  onToggle: (key: ColKey) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onDown)
    return () => window.removeEventListener('mousedown', onDown)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1 text-[12px] font-medium text-fg-muted hover:bg-raised"
      >
        <Columns3 size={13} strokeWidth={1.8} /> Columns
        <ChevronDown size={12} className={open ? 'rotate-180' : ''} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 w-44 rounded-lg border border-border bg-surface p-1 shadow-xl">
          {COLUMNS.filter((c) => c.key !== 'website').map((c) => (
            <label
              key={c.key}
              className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[12px] text-fg-muted hover:bg-raised"
            >
              <input
                type="checkbox"
                checked={!hidden.has(c.key)}
                onChange={() => onToggle(c.key)}
                className="accent-brand"
              />
              {c.label}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export function ProspectsTable({
  prospects,
  selectedId,
  onSelect,
  sort,
  onSort,
}: {
  prospects: Prospect[]
  selectedId: number | null
  onSelect: (p: Prospect) => void
  sort: SortState | null
  onSort: (key: ColKey) => void
}) {
  const [hidden, setHidden] = useState<Set<ColKey>>(new Set())

  const visible = COLUMNS.filter((c) => !hidden.has(c.key))
  // Rows arrive already sorted by the API (server-side over the WHOLE dataset, not the page).
  const rows = prospects

  function toggleCol(key: ColKey) {
    setHidden((h) => {
      const next = new Set(h)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between border-b border-border bg-surface px-3 py-1.5">
        <span className="text-[11px] text-fg-subtle">
          {sort
            ? `Sorted by ${sort.key.replace('_', ' ')} (${sort.dir})`
            : 'Sorted by trust · click a header to sort'}
        </span>
        <ColumnsMenu hidden={hidden} onToggle={toggleCol} />
      </div>

      <div className="flex-1 overflow-auto">
        <table className="w-full border-separate border-spacing-0 text-[13px]">
          <thead>
            <tr>
              {visible.map((col) => {
                const frozen = col.key === 'website'
                const active = sort?.key === col.key
                return (
                  <th
                    key={col.key}
                    className={`${TH} ${col.right ? 'text-right' : ''} ${frozen ? 'left-0 z-20' : ''}`}
                  >
                    {col.sortable ? (
                      <button
                        type="button"
                        onClick={() => onSort(col.key)}
                        className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-fg"
                      >
                        {col.label}
                        {active ? (
                          sort.dir === 'asc' ? (
                            <ChevronUp size={12} />
                          ) : (
                            <ChevronDown size={12} />
                          )
                        ) : (
                          <ArrowUpDown size={11} className="opacity-40" />
                        )}
                      </button>
                    ) : (
                      col.label
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const selected = p.id === selectedId
              return (
                <tr
                  key={p.id}
                  onClick={() => onSelect(p)}
                  className={`group cursor-pointer ${selected ? 'bg-brand/5' : ''}`}
                >
                  {visible.map((col) => {
                    const frozen = col.key === 'website'
                    return (
                      <td
                        key={col.key}
                        className={`${TD} ${col.right ? 'text-right' : ''} ${
                          frozen
                            ? `sticky left-0 z-10 font-medium text-fg ${selected ? 'bg-brand/5' : 'bg-surface'}`
                            : ''
                        }`}
                      >
                        {col.render(p)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
