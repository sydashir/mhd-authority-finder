import type { GeoLevel, SourceTag, TrustBand } from '../api/types'

export interface ProspectQueryFilters {
  contact_trust?: TrustBand
  source_tag?: SourceTag
  level?: GeoLevel
}

const TRUST_OPTS = [
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]
const SOURCE_OPTS = [
  { value: 'MHD', label: 'MHD' },
  { value: 'AH', label: 'AH' },
]
const LEVEL_OPTS = [
  { value: 'state', label: 'State' },
  { value: 'county', label: 'County' },
  { value: 'city', label: 'City' },
]

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string | undefined
  options: { value: string; label: string }[]
  onChange: (value: string | undefined) => void
}) {
  const active = value !== undefined
  return (
    <label className="flex items-center gap-1.5 text-[12px]">
      <span className="text-zinc-500">{label}</span>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || undefined)}
        className={`cursor-pointer rounded-md border px-2 py-1 text-[12px] outline-none focus:ring-2 focus:ring-indigo-500/30 ${
          active
            ? 'border-indigo-300 bg-indigo-50/60 font-medium text-indigo-700'
            : 'border-zinc-200 bg-white text-zinc-600'
        }`}
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export function FilterBar({
  filters,
  onChange,
  onReset,
  activeCount,
}: {
  filters: ProspectQueryFilters
  onChange: (patch: Partial<ProspectQueryFilters>) => void
  onReset: () => void
  activeCount: number
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-zinc-200 bg-white px-4 py-2.5">
      <span className="text-[11px] font-medium uppercase tracking-wide text-zinc-400">Filters</span>
      <Select
        label="Trust"
        value={filters.contact_trust}
        options={TRUST_OPTS}
        onChange={(v) => onChange({ contact_trust: v as TrustBand | undefined })}
      />
      <Select
        label="Source"
        value={filters.source_tag}
        options={SOURCE_OPTS}
        onChange={(v) => onChange({ source_tag: v as SourceTag | undefined })}
      />
      <Select
        label="Level"
        value={filters.level}
        options={LEVEL_OPTS}
        onChange={(v) => onChange({ level: v as GeoLevel | undefined })}
      />
      {activeCount > 0 && (
        <button
          type="button"
          onClick={onReset}
          className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700"
        >
          Reset ({activeCount})
        </button>
      )}
    </div>
  )
}
