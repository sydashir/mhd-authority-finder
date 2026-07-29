import { Plus } from 'lucide-react'

/**
 * The District Behavioral Health directories the tool watches, with the exact geo URL shape
 * it recognises on each. This replaced a strip of dataset counts: those drift every time the
 * pipeline runs, while the properties being watched are the stable, meaningful fact.
 *
 * Values mirror `authority_finder/geo_monitor/sites.py` (the source of truth) so the page
 * cannot claim to watch something the tool does not.
 */

const PROPERTIES = [
  {
    tag: 'MHD',
    name: 'Inpatient Mental Health Finder',
    domain: 'inpatientmentalhealthfinder.com',
    pattern: '/serving/{state}/{county}/{city}',
    badge: 'badge-mhd',
  },
  {
    tag: 'AH',
    name: 'Addiction Hotline',
    domain: 'addictionhotline.com',
    pattern: '/{state}/{county}/{city}',
    badge: 'badge-ah',
  },
]

export function WatchedProperties() {
  return (
    <div>
      <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand">
        District Behavioral Health
      </span>
      <h2 className="mt-3 max-w-[26ch] text-[22px] font-semibold leading-snug tracking-[-0.01em] text-fg sm:text-[26px]">
        The directories it watches for new geo pages.
      </h2>

      <ul className="mt-5 grid gap-4 md:grid-cols-[1fr_1fr_auto]">
        {PROPERTIES.map((property) => (
          <li key={property.tag} className="scan-card card card-interactive relative p-5">
            <div className="flex items-center gap-2.5">
              <span className={`badge ${property.badge} font-semibold`}>{property.tag}</span>
              <span className="ml-auto flex items-center gap-1.5 text-[11px] text-fg-subtle">
                <span className="live-dot h-1.5 w-1.5 rounded-full bg-brand" aria-hidden />
                Watching
              </span>
            </div>
            <h3 className="mt-3.5 text-[14.5px] font-semibold leading-snug text-fg">
              {property.name}
            </h3>
            <p className="mt-1 truncate text-[12.5px] text-fg-muted">{property.domain}</p>
            <p
              className="mt-3 truncate border-t border-border pt-3 text-[11.5px] text-fg-subtle"
              style={{ fontFamily: 'var(--font-mono)' }}
              title={`Geo pages matching ${property.pattern}`}
            >
              {property.pattern}
            </p>
          </li>
        ))}

        {/* The tool takes a site config per property, so the portfolio can grow. */}
        <li className="flex min-w-[190px] flex-col justify-center rounded-[14px] border border-dashed border-border p-5 text-fg-subtle">
          <Plus size={16} className="text-brand" />
          <p className="mt-2.5 text-[12.5px] leading-relaxed">
            Another District property drops in as one config entry.
          </p>
        </li>
      </ul>
    </div>
  )
}
