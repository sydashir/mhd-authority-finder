import { useEffect, useState, type ReactNode } from 'react'
import type { Prospect } from '../api/types'
import { competitorList, formatDate, formatPopulation, pagePath } from '../lib/format'
import { ConfidenceTag, SourceBadge, TrustBadge } from './badges'

function Labeled({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">{label}</span>
      {children}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
        {title}
      </h3>
      <dl className="divide-y divide-zinc-100 overflow-hidden rounded-md border border-zinc-200">
        {children}
      </dl>
    </section>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3 px-3 py-2">
      <dt className="text-[12px] text-zinc-400">{label}</dt>
      <dd className="min-w-0 break-words text-[13px] text-zinc-700">{children}</dd>
    </div>
  )
}

function DrawerContent({ prospect: p, onClose }: { prospect: Prospect; onClose: () => void }) {
  const competitors = competitorList(p.competitor_links)
  return (
    <>
      <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold text-zinc-900">{p.website}</div>
          <div className="mt-0.5 text-[12px] text-zinc-400">Prospect #{p.id}</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-mr-1 rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
        >
          <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="m4 4 8 8M12 4l-8 8" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      <div className="flex-1 space-y-5 overflow-auto px-5 py-4">
        <div className="flex gap-6">
          <Labeled label="Contact Trust">
            <TrustBadge band={p.contact_trust} />
          </Labeled>
          <Labeled label="Confidence">
            <ConfidenceTag band={p.confidence} />
          </Labeled>
          <Labeled label="Source">
            <SourceBadge source={p.source_tag} />
          </Labeled>
        </div>

        <Section title="Contact">
          <Row label="Email">
            {p.email ? (
              <a href={`mailto:${p.email}`} className="text-indigo-600 hover:underline">
                {p.email}
              </a>
            ) : (
              <span className="text-zinc-300">—</span>
            )}
          </Row>
          <Row label="Phone">
            {p.phone ? (
              <a href={`tel:${p.phone}`} className="tnum text-zinc-700 hover:underline">
                {p.phone}
              </a>
            ) : (
              <span className="text-zinc-300">—</span>
            )}
          </Row>
          <Row label="Provenance">{p.contact_source || <span className="text-zinc-300">—</span>}</Row>
        </Section>

        <Section title="Page">
          <Row label="Specific page">
            <a
              href={p.specific_page}
              target="_blank"
              rel="noreferrer"
              className="text-indigo-600 hover:underline"
            >
              {pagePath(p.specific_page)} ↗
            </a>
          </Row>
          <Row label="Organization">
            {p.organization_description || <span className="text-zinc-300">—</span>}
          </Row>
        </Section>

        <Section title="Geography">
          <Row label="Geo served">{p.geo_served}</Row>
          <Row label="Population">
            <span className="tnum">{formatPopulation(p.population)}</span>
          </Row>
        </Section>

        <Section title="Competitor links">
          <div className="px-3 py-2">
            {competitors.length === 0 ? (
              <span className="text-[13px] text-zinc-400">None detected</span>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {competitors.map((domain) => (
                  <li
                    key={domain}
                    className="rounded bg-rose-50 px-1.5 py-0.5 text-[12px] font-medium text-rose-700 ring-1 ring-inset ring-rose-600/20"
                  >
                    {domain}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Section>

        <Section title="Record">
          <Row label="Added">{formatDate(p.date_added)}</Row>
          <Row label="Run">{p.run_id ?? <span className="text-zinc-300">—</span>}</Row>
        </Section>
      </div>
    </>
  )
}

export function ProspectDrawer({
  prospect,
  onClose,
}: {
  prospect: Prospect | null
  onClose: () => void
}) {
  const open = prospect !== null
  // Retain the last prospect so content stays visible through the slide-out.
  const [shown, setShown] = useState<Prospect | null>(prospect)
  useEffect(() => {
    if (prospect) setShown(prospect)
  }, [prospect])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <div className={`fixed inset-0 z-40 ${open ? '' : 'pointer-events-none'}`} aria-hidden={!open}>
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-zinc-900/20 transition-opacity duration-200 ${
          open ? 'opacity-100' : 'opacity-0'
        }`}
      />
      <aside
        className={`absolute top-0 right-0 flex h-full w-full max-w-[440px] flex-col bg-white shadow-xl ring-1 ring-zinc-200 transition-transform duration-200 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-label="Prospect detail"
      >
        {shown && <DrawerContent prospect={shown} onClose={onClose} />}
      </aside>
    </div>
  )
}
