import {
  Check,
  Copy,
  ExternalLink,
  Loader2,
  Mail,
  Phone,
  Save,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useSetOutreach } from '../api/hooks'
import type { OutreachStatus, Prospect, TrustBand } from '../api/types'
import { competitorList, formatDate, formatPopulation, OUTREACH_LABELS, timeAgo } from '../lib/format'
import { OutreachBadge, SourceBadge, TrustBadge } from './badges'
import type { ToastData } from './Toast'

function trustExplanation(band: TrustBand): string {
  if (band === 'high')
    return 'A department or role inbox on the organization’s own domain — safe to reach out.'
  if (band === 'medium')
    return 'A same-domain contact, but a general inbox — usable; double-check the recipient.'
  return 'Best-effort contact (role / other department, or off-domain) — verify before outreach.'
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      aria-label={`Copy ${label}`}
      onClick={() => {
        void navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      }}
      className="inline-flex items-center justify-center rounded-md border border-border bg-surface p-1.5 text-fg-subtle hover:bg-raised hover:text-fg"
    >
      {copied ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
    </button>
  )
}

const ACTION =
  'inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1.5 text-[12px] font-medium text-fg-muted hover:bg-raised hover:text-fg'

function ContactField({
  label,
  value,
  href,
  hrefIcon,
  hrefLabel,
}: {
  label: string
  value: string
  href: string
  hrefIcon: ReactNode
  hrefLabel: string
}) {
  if (!value) {
    return (
      <div className="rounded-lg border border-border bg-surface px-3 py-2.5">
        <div className="text-[10px] font-medium uppercase tracking-wide text-fg-subtle">{label}</div>
        <div className="mt-0.5 text-[13px] text-fg-subtle">Not found</div>
      </div>
    )
  }
  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2.5">
      <div className="text-[10px] font-medium uppercase tracking-wide text-fg-subtle">{label}</div>
      <div className="mt-1 flex items-center gap-2">
        <div className="min-w-0 flex-1 truncate text-[13px] text-fg" title={value}>
          {value}
        </div>
        <CopyButton text={value} label={label} />
        <a href={href} className={ACTION}>
          {hrefIcon}
          {hrefLabel}
        </a>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
        {title}
      </h3>
      {children}
    </section>
  )
}

function MetaRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 text-[13px]">
      <span className="text-fg-subtle">{label}</span>
      <span className="min-w-0 truncate text-right text-fg">{children}</span>
    </div>
  )
}

function rootUrl(website: string): string {
  return website.startsWith('http') ? website : `https://${website}`
}

/** The team's workspace on a prospect (ADR-022) — set the status, log a note. */
function OutreachSection({
  prospect: p,
  notify,
}: {
  prospect: Prospect
  notify: (toast: ToastData) => void
}) {
  const mutation = useSetOutreach()
  const [status, setStatus] = useState<OutreachStatus>(p.outreach_status)
  const [notes, setNotes] = useState(p.outreach_notes)
  // The saved baseline — updated on a successful save so the pill + dirty-state track reality
  // even though the parent's selected-prospect snapshot doesn't refresh until reopened.
  const [savedStatus, setSavedStatus] = useState<OutreachStatus>(p.outreach_status)
  const [savedNotes, setSavedNotes] = useState(p.outreach_notes)
  const [savedBy, setSavedBy] = useState(p.outreach_updated_by)
  const [savedAt, setSavedAt] = useState(p.outreach_updated_at)

  useEffect(() => {
    setStatus(p.outreach_status)
    setNotes(p.outreach_notes)
    setSavedStatus(p.outreach_status)
    setSavedNotes(p.outreach_notes)
    setSavedBy(p.outreach_updated_by)
    setSavedAt(p.outreach_updated_at)
  }, [p.id, p.outreach_status, p.outreach_notes, p.outreach_updated_by, p.outreach_updated_at])

  const dirty = status !== savedStatus || notes !== savedNotes

  function save() {
    mutation.mutate(
      { id: p.id, status, notes },
      {
        onSuccess: (updated) => {
          setSavedStatus(updated.outreach_status)
          setSavedNotes(updated.outreach_notes)
          setSavedBy(updated.outreach_updated_by)
          setSavedAt(updated.outreach_updated_at)
          notify({ message: 'Outreach updated.', tone: 'success' })
        },
        onError: () => notify({ message: 'Couldn’t save outreach — try again.', tone: 'error' }),
      },
    )
  }

  return (
    <Section title="Outreach">
      <div className="space-y-3 rounded-xl border border-border bg-raised/40 p-4">
        <div className="flex items-center gap-2">
          <OutreachBadge status={savedStatus} />
          {savedBy && (
            <span className="ml-auto truncate text-[11px] text-fg-subtle" title={savedBy}>
              {savedBy}
              {savedAt ? ` · ${timeAgo(savedAt)}` : ''}
            </span>
          )}
        </div>
        <label className="block">
          <span className="text-[10px] font-medium uppercase tracking-wide text-fg-subtle">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as OutreachStatus)}
            className="mt-1 w-full cursor-pointer rounded-md border border-border bg-app px-2 py-1.5 text-[13px] text-fg outline-none focus:ring-2 focus:ring-brand/25"
          >
            {(Object.keys(OUTREACH_LABELS) as OutreachStatus[]).map((s) => (
              <option key={s} value={s}>
                {OUTREACH_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[10px] font-medium uppercase tracking-wide text-fg-subtle">Notes</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Notes on the conversation…"
            className="mt-1 w-full resize-y rounded-md border border-border bg-app px-2 py-1.5 text-[13px] text-fg outline-none placeholder:text-fg-subtle focus:ring-2 focus:ring-brand/25"
          />
        </label>
        <button
          type="button"
          onClick={save}
          disabled={!dirty || mutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-[12px] font-medium text-brand-fg hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          {mutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          {dirty ? 'Save' : 'Saved'}
        </button>
      </div>
    </Section>
  )
}

function DrawerContent({
  prospect: p,
  onClose,
  notify,
}: {
  prospect: Prospect
  onClose: () => void
  notify: (toast: ToastData) => void
}) {
  const competitors = competitorList(p.competitor_links)
  return (
    <>
      <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div className="min-w-0">
          <div className="truncate text-[16px] font-semibold text-fg">{p.website}</div>
          <a
            href={rootUrl(p.website)}
            target="_blank"
            rel="noreferrer"
            className="mt-0.5 inline-flex items-center gap-1 text-[12px] text-brand hover:underline"
          >
            Visit site <ExternalLink size={11} />
          </a>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="-mr-1 rounded-md p-1.5 text-fg-subtle hover:bg-raised hover:text-fg"
        >
          <X size={16} strokeWidth={1.8} />
        </button>
      </header>

      <div className="flex-1 space-y-5 overflow-auto px-5 py-4">
        {/* Trust panel — the "why we trust this" rationale */}
        <div className="rounded-xl border border-border bg-raised/40 p-4">
          <div className="flex items-center gap-2">
            <ShieldCheck size={15} className="text-fg-muted" />
            <TrustBadge band={p.contact_trust} />
            <span className="text-[11px] text-fg-subtle">contact trust</span>
            <span className="ml-auto">
              <SourceBadge source={p.source_tag} />
            </span>
          </div>
          <p className="mt-2.5 text-[12px] leading-relaxed text-fg-muted">
            {trustExplanation(p.contact_trust)}
          </p>
          <div className="mt-2 text-[11px] text-fg-subtle">
            Source: <span className="text-fg-muted">{p.contact_source || 'unknown'}</span> · Page
            confidence <span className="capitalize text-fg-muted">{p.confidence}</span>
          </div>
        </div>

        <OutreachSection prospect={p} notify={notify} />

        <Section title="Contact">
          <div className="space-y-2">
            <ContactField
              label="Email"
              value={p.email}
              href={`mailto:${p.email}`}
              hrefIcon={<Mail size={13} />}
              hrefLabel="Email"
            />
            <ContactField
              label="Phone"
              value={p.phone}
              href={`tel:${p.phone}`}
              hrefIcon={<Phone size={13} />}
              hrefLabel="Call"
            />
          </div>
        </Section>

        <Section title="Resource page">
          <a
            href={p.specific_page}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2.5 text-[13px] text-brand hover:bg-raised"
          >
            <ExternalLink size={14} className="shrink-0" />
            <span className="min-w-0 flex-1 truncate" title={p.specific_page}>
              {p.specific_page}
            </span>
          </a>
          {p.organization_description && (
            <p className="mt-2 text-[12px] leading-relaxed text-fg-muted">
              {p.organization_description}
            </p>
          )}
        </Section>

        <Section title="Competitor links">
          {competitors.length === 0 ? (
            <div className="rounded-lg border border-border bg-surface px-3 py-2.5 text-[13px] text-fg-subtle">
              None detected — no links to competitor directories on this page.
            </div>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {competitors.map((domain) => (
                <li key={domain} className="badge badge-flag">
                  {domain}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Details">
          <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
            <MetaRow label="Geo served">{p.geo_served}</MetaRow>
            <MetaRow label="Population">
              <span className="tnum">{formatPopulation(p.population)}</span>
            </MetaRow>
            <MetaRow label="Date added">{formatDate(p.date_added)}</MetaRow>
            <MetaRow label="Run">{p.run_id ?? '—'}</MetaRow>
          </div>
        </Section>
      </div>
    </>
  )
}

export function ProspectDrawer({
  prospect,
  onClose,
  notify,
}: {
  prospect: Prospect | null
  onClose: () => void
  notify: (toast: ToastData) => void
}) {
  const open = prospect !== null
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
        className={`absolute inset-0 bg-black/50 transition-opacity duration-200 ${
          open ? 'opacity-100' : 'opacity-0'
        }`}
      />
      <aside
        className={`absolute top-0 right-0 flex h-full w-full max-w-[460px] flex-col border-l border-border bg-surface shadow-2xl transition-transform duration-200 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-label="Prospect detail"
      >
        {shown && <DrawerContent prospect={shown} onClose={onClose} notify={notify} />}
      </aside>
    </div>
  )
}
