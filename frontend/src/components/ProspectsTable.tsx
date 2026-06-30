import type { Prospect } from '../api/types'
import { competitorList, formatPopulation, orDash, pagePath } from '../lib/format'
import { ConfidenceTag, SourceBadge, TrustBadge } from './badges'

const TH =
  'sticky top-0 z-10 border-b border-zinc-200 bg-zinc-50 px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wide text-zinc-500 whitespace-nowrap'
const TD = 'border-b border-zinc-100 px-3 py-1.5 align-middle group-hover:bg-indigo-50/40'

function CompetitorCell({ raw }: { raw: string }) {
  const links = competitorList(raw)
  if (links.length === 0) return <span className="text-zinc-300">—</span>
  return (
    <span
      title={links.join(', ')}
      className="inline-flex items-center gap-1 rounded bg-rose-50 px-1.5 py-0.5 text-[11px] font-medium text-rose-700 ring-1 ring-inset ring-rose-600/20"
    >
      <svg viewBox="0 0 16 16" className="h-3 w-3" fill="currentColor" aria-hidden>
        <path d="M3 1.5a.75.75 0 0 1 .75.75v.34l8.36 2.39a.5.5 0 0 1 0 .96L4.5 8.06v6.19a.75.75 0 0 1-1.5 0V2.25A.75.75 0 0 1 3 1.5Z" />
      </svg>
      {links.length}
    </span>
  )
}

export function ProspectsTable({
  prospects,
  selectedId,
  onSelect,
}: {
  prospects: Prospect[]
  selectedId: number | null
  onSelect: (p: Prospect) => void
}) {
  return (
    <table className="w-full border-separate border-spacing-0 text-[13px]">
      <thead>
          <tr>
            <th className={`${TH} left-0 z-20`}>Website</th>
            <th className={TH}>Specific Page</th>
            <th className={TH}>Email</th>
            <th className={TH}>Phone</th>
            <th className={TH}>Trust</th>
            <th className={TH}>Geo Served</th>
            <th className={TH}>Source</th>
            <th className={TH}>Competitors</th>
            <th className={`${TH} text-right`}>Population</th>
            <th className={TH}>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {prospects.map((p) => {
            const selected = p.id === selectedId
            return (
              <tr
                key={p.id}
                onClick={() => onSelect(p)}
                className={`group cursor-pointer ${selected ? 'bg-indigo-50/60' : ''}`}
              >
                <td
                  className={`${TD} sticky left-0 z-10 font-medium text-zinc-800 ${selected ? 'bg-indigo-50/60' : 'bg-white'}`}
                >
                  <div className="max-w-[180px] truncate" title={p.website}>
                    {p.website}
                  </div>
                </td>
                <td className={TD}>
                  <a
                    href={p.specific_page}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    title={p.specific_page}
                    className="block max-w-[230px] truncate text-indigo-600 hover:underline"
                  >
                    {pagePath(p.specific_page)}
                  </a>
                </td>
                <td className={TD}>
                  <div className="max-w-[200px] truncate text-zinc-600" title={p.email}>
                    {orDash(p.email)}
                  </div>
                </td>
                <td className={`${TD} tnum whitespace-nowrap text-zinc-600`}>{orDash(p.phone)}</td>
                <td className={TD}>
                  <TrustBadge band={p.contact_trust} />
                </td>
                <td className={TD}>
                  <div className="max-w-[170px] truncate text-zinc-600" title={p.geo_served}>
                    {p.geo_served}
                  </div>
                </td>
                <td className={TD}>
                  <SourceBadge source={p.source_tag} />
                </td>
                <td className={TD}>
                  <CompetitorCell raw={p.competitor_links} />
                </td>
                <td className={`${TD} tnum whitespace-nowrap text-right text-zinc-700`}>
                  {formatPopulation(p.population)}
                </td>
                <td className={TD}>
                  <ConfidenceTag band={p.confidence} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
  )
}
