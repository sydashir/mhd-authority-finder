import {
  ArrowRight,
  CircleCheck,
  FileSearch,
  Link2,
  MapPin,
  Moon,
  Radar,
  Search,
  ShieldCheck,
  Sun,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTheme } from '../../lib/theme'
import { useReveal } from '../../lib/useReveal'
import { Logo } from '../Logo'
import { PipelineTrace } from './PipelineTrace'
import { RadarScan } from './RadarScan'
import { WatchedProperties } from './WatchedProperties'
import { SignInDialog } from './SignInDialog'

/**
 * The public face of AuthorityScout: what the tool does, on the tool's own visual
 * language (the teal-on-slate scope identity the workspace already uses), and the
 * door into it.
 *
 * Every figure on this page is read from the live dataset, never invented. Motion is
 * limited to the radar sweep (which depicts the product's actual job) and one reveal
 * per section; both stand still under prefers-reduced-motion.
 */

// The 16 competitor domains from the brief, checked on every prospect.
const COMPETITORS = [
  'samhsa.gov',
  'rehabnet.com',
  'recovery.com',
  'rehabs.com',
  'drugrehabus.org',
  'addictions.com',
  'naatp.org',
  'findtreatment.gov',
  'addictioncenter.com',
  'startyourrecovery.org',
  'addictionresource.net',
  'addictionresource.com',
  'betteraddictioncare.com',
  'rehabs.org',
  'drugabuse.com',
  'treatmentatlas.org',
]

// What each contact-trust band actually means (ADR-010), which beats a row count that
// changes on every run.
const TRUST_BANDS = [
  {
    label: 'High',
    cls: 'badge-high',
    meaning: 'A department inbox on the organization\u2019s own domain.',
  },
  {
    label: 'Medium',
    cls: 'badge-medium',
    meaning: 'A general inbox, or a department reached through a contact page.',
  },
  {
    label: 'Low',
    cls: 'badge-low',
    meaning: 'A role address, an off-domain contact, or a phone number only.',
  },
]

// Real wrong-state catches from the ADR-024 audit.
const REJECTED = [
  { domain: 'vaughn.edu', actually: 'New York', filedUnder: 'Alaska' },
  { domain: 'tamiu.edu', actually: 'Texas', filedUnder: 'Hawaii' },
  { domain: 'dconc.gov', actually: 'North Carolina', filedUnder: 'Irvine, California' },
  { domain: 'iup.edu', actually: 'Pennsylvania', filedUnder: 'Indiana' },
]

const STEPS = [
  {
    icon: Radar,
    title: 'Watch the sitemaps',
    body: 'Both directories are polled on a schedule. A newly published geo page starts a run on its own.',
  },
  {
    icon: Search,
    title: 'Search that geography',
    body: 'Targeted queries per city, county, and state. Only .gov and .edu domains carry forward.',
  },
  {
    icon: MapPin,
    title: 'Prove the geography',
    body: 'A domain that belongs to another state is rejected outright, not flagged and shipped anyway.',
  },
  {
    icon: FileSearch,
    title: 'Find the real page',
    body: 'The health department or student resource page, scored against the homepage it is not.',
  },
  {
    icon: ShieldCheck,
    title: 'Pull a usable contact',
    body: 'Same domain inbox first, graded high, medium, or low so you know what you are sending to.',
  },
  {
    icon: Link2,
    title: 'Flag the competition',
    body: 'Sixteen directories are checked. If the site already links to one, the row says which.',
  },
]

function Section({
  children,
  className = '',
  id,
}: {
  children: ReactNode
  className?: string
  id?: string
}) {
  const { ref, shown } = useReveal()
  return (
    <section
      id={id}
      ref={ref}
      className={`reveal ${shown ? 'reveal-in' : ''} mx-auto w-full max-w-[1180px] px-5 sm:px-8 ${className}`}
    >
      {children}
    </section>
  )
}

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand">
      {children}
    </span>
  )
}

export function Landing() {
  const { theme, toggle } = useTheme()
  const [signInOpen, setSignInOpen] = useState(false)
  const open = () => setSignInOpen(true)

  return (
    <div className="min-h-[100dvh] overflow-x-hidden bg-app">
      {/* NAV: one line, 64px, never wraps. */}
      <header className="sticky top-0 z-40 border-b border-border/70 bg-app/85 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-[1180px] items-center gap-6 px-5 sm:px-8">
          <span className="flex items-center gap-2 font-semibold tracking-tight text-fg">
            <span className="text-brand">
              <Logo size={22} />
            </span>
            AuthorityScout
          </span>
          <div className="ml-auto hidden items-center gap-7 text-[13px] text-fg-muted md:flex">
            <a href="#how" className="transition-colors hover:text-fg">
              How it works
            </a>
            <a href="#trace" className="transition-colors hover:text-fg">
              See a run
            </a>
            <a href="#precision" className="transition-colors hover:text-fg">
              Precision
            </a>
          </div>
          <button
            type="button"
            onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            className="ml-auto rounded-md p-2 text-fg-subtle transition-colors hover:bg-raised hover:text-fg md:ml-0"
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button
            type="button"
            onClick={open}
            className="rounded-lg bg-brand px-3.5 py-1.5 text-[13px] font-semibold text-brand-fg transition-all hover:bg-brand-strong active:scale-[0.98]"
          >
            Sign in
          </button>
        </nav>
      </header>

      {/* HERO: asymmetric split. Headline, one paragraph, two actions. Nothing else. */}
      <Section className="grid items-center gap-12 pb-4 pt-14 sm:pt-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
        <div>
          <h1 className="max-w-[24ch] text-[36px] font-semibold leading-[1.06] tracking-[-0.02em] text-fg sm:text-[46px] lg:text-[52px]">
            Local authority sites, ready to contact.
          </h1>
          <p className="mt-5 max-w-[52ch] text-[15px] leading-relaxed text-fg-muted sm:text-[16px]">
            AuthorityScout scans every geo page on your directories, verifies the organization is
            local, and pulls a contact you can email.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={open}
              className="inline-flex items-center gap-2 whitespace-nowrap rounded-lg bg-brand px-5 py-2.5 text-[14px] font-semibold text-brand-fg transition-all hover:bg-brand-strong active:scale-[0.99]"
            >
              Sign in <ArrowRight size={15} />
            </button>
            <a
              href="#how"
              className="inline-flex items-center gap-2 whitespace-nowrap rounded-lg border border-border-strong px-5 py-2.5 text-[14px] font-medium text-fg transition-colors hover:bg-raised"
            >
              See how it works
            </a>
          </div>
        </div>
        <RadarScan />
      </Section>

      {/* WATCHED PROPERTIES: the brands this runs for, which do not go stale like counts do. */}
      <Section className="pb-20 pt-12 sm:pb-24">
        <WatchedProperties />
      </Section>

      {/* HOW IT WORKS: a connected rail, one step per stage of the real pipeline. */}
      <Section id="how" className="pb-20 sm:pb-28">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="mt-3 max-w-[22ch] text-[28px] font-semibold leading-tight tracking-[-0.015em] text-fg sm:text-[36px]">
          From a new geo page to a contact you can email.
        </h2>
        <ol className="mt-12 grid gap-x-10 gap-y-9 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step) => (
            <li key={step.title} className="flex gap-4">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-brand">
                <step.icon size={16} strokeWidth={1.9} />
              </span>
              <div>
                <h3 className="text-[14.5px] font-semibold text-fg">{step.title}</h3>
                <p className="mt-1.5 max-w-[42ch] text-[13.5px] leading-relaxed text-fg-muted">
                  {step.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </Section>

      {/* TRACE: the pipeline running on one real page, in place of a static screenshot. */}
      <Section id="trace" className="pb-20 sm:pb-28">
        <PipelineTrace />
      </Section>

      {/* PRECISION: asymmetric bento, four cells for four claims. */}
      <Section id="precision" className="pb-20 sm:pb-28">
        <Eyebrow>Built for precision</Eyebrow>
        <h2 className="mt-3 max-w-[24ch] text-[28px] font-semibold leading-tight tracking-[-0.015em] text-fg sm:text-[36px]">
          A wrong row costs more than a missing one.
        </h2>

        <div className="mt-11 grid gap-4 lg:grid-cols-3">
          <article className="card card-interactive relative overflow-hidden p-7 lg:col-span-2 lg:row-span-2">
            <div
              className="pointer-events-none absolute inset-0 opacity-70"
              style={{
                background:
                  'radial-gradient(120% 90% at 90% 0%, var(--brand-soft), transparent 60%)',
              }}
              aria-hidden
            />
            <div className="relative">
              <MapPin size={20} className="text-brand" strokeWidth={1.9} />
              <h3 className="mt-4 text-[17px] font-semibold text-fg">
                Geography is proven, not assumed
              </h3>
              <p className="mt-2 max-w-[52ch] text-[13.5px] leading-relaxed text-fg-muted">
                A New York university does not belong under an Alaska page. Domains are checked
                against the geography they are being filed under, and a contradiction is rejected
                before it reaches your list.
              </p>
              {/* Real rejections from that audit, shown the way the checker saw them. */}
              <ul className="mt-6 space-y-px overflow-hidden rounded-lg border border-border">
                {REJECTED.map((row) => (
                  <li
                    key={row.domain}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 bg-app/60 px-3.5 py-2.5 text-[12.5px]"
                  >
                    <span className="text-fg" style={{ fontFamily: 'var(--font-mono)' }}>
                      {row.domain}
                    </span>
                    <span className="text-fg-subtle">is {row.actually}</span>
                    <span className="ml-auto flex items-center gap-2 text-fg-subtle">
                      filed under {row.filedUnder}
                      <span className="badge badge-flag">rejected</span>
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-[12.5px] leading-relaxed text-fg-subtle">
                The domain decides, not the wording on the page. Indiana University of Pennsylvania
                reads like Indiana and is checked as Pennsylvania.
              </p>
            </div>
          </article>

          <article className="card card-interactive p-6">
            <ShieldCheck size={18} className="text-brand" strokeWidth={1.9} />
            <h3 className="mt-3.5 text-[15px] font-semibold text-fg">Every contact is graded</h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-fg-muted">
              You know which are safe to mail before you open the row.
            </p>
            <dl className="mt-5 space-y-2.5">
              {TRUST_BANDS.map((band) => (
                <div key={band.label} className="flex gap-3">
                  <dt className={`badge ${band.cls} h-fit w-[74px] shrink-0 justify-center`}>
                    {band.label}
                  </dt>
                  <dd className="flex-1 text-[12.5px] leading-snug text-fg-muted">
                    {band.meaning}
                  </dd>
                </div>
              ))}
            </dl>
          </article>

          <article className="card card-interactive p-6">
            <Link2 size={18} className="text-brand" strokeWidth={1.9} />
            <h3 className="mt-3.5 text-[15px] font-semibold text-fg">
              You see who already links out
            </h3>
            <p className="mt-1.5 text-[13px] leading-relaxed text-fg-muted">
              Sixteen competing directories are checked on every prospect. A site that already links
              to one is a warm opening rather than a cold one, and the row names which.
            </p>
          </article>
        </div>
      </Section>

      {/* CHECKED AGAINST: the one marquee on the page, carrying the real 16 domains. */}
      <section className="border-y border-border py-9">
        <p className="mx-auto mb-6 max-w-[1180px] px-5 text-[12.5px] text-fg-subtle sm:px-8">
          Every prospect is checked against the directories you compete with
        </p>
        <div className="marquee-mask relative flex overflow-hidden">
          <div className="marquee-track flex shrink-0 items-center gap-3 pr-3">
            {[...COMPETITORS, ...COMPETITORS].map((domain, i) => (
              <span
                key={`${domain}-${i}`}
                className="whitespace-nowrap rounded-full border border-border bg-surface px-3.5 py-1.5 text-[12.5px] text-fg-muted"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {domain}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* SIGN IN */}
      <Section className="py-20 sm:py-28">
        <div className="card relative overflow-hidden px-7 py-12 text-center sm:px-12 sm:py-16">
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background: 'radial-gradient(90% 120% at 50% 0%, var(--brand-soft), transparent 65%)',
            }}
            aria-hidden
          />
          <div className="relative">
            <h2 className="mx-auto max-w-[20ch] text-[26px] font-semibold leading-tight tracking-[-0.015em] text-fg sm:text-[32px]">
              Your prospects are waiting in the workspace.
            </h2>
            <p className="mx-auto mt-3 max-w-[46ch] text-[14px] text-fg-muted">
              Filtered, graded, and geography checked, ready for the next outreach round.
            </p>
            <button
              type="button"
              onClick={open}
              className="mt-8 inline-flex items-center gap-2 whitespace-nowrap rounded-lg bg-brand px-6 py-3 text-[14px] font-semibold text-brand-fg transition-all hover:bg-brand-strong active:scale-[0.99]"
            >
              Sign in <ArrowRight size={15} />
            </button>
            <p className="mt-4 flex items-center justify-center gap-1.5 text-[12px] text-fg-subtle">
              <CircleCheck size={13} /> No Google account needed
            </p>
          </div>
        </div>
      </Section>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-3 px-5 py-8 text-[12.5px] text-fg-subtle sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span className="flex items-center gap-2">
            <span className="text-brand">
              <Logo size={16} />
            </span>
            AuthorityScout
          </span>
          <span>
            Backlink prospecting for District Behavioral Health, across Inpatient Mental Health
            Finder and Addiction Hotline.
          </span>
        </div>
      </footer>

      <SignInDialog open={signInOpen} onClose={() => setSignInOpen(false)} />
    </div>
  )
}
