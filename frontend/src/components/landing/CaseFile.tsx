import { Check, Flag, Play, RotateCcw, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { useReveal } from '../../lib/useReveal'

/**
 * One real run, and the row it refused to write.
 *
 * Addiction Hotline published a North Dakota page. Eleven domains reached the last check.
 * One of them was dsu.edu — Dakota State University, which is in SOUTH Dakota, and which
 * shipped at high trust in the S21 run with a 605 phone number. The campus-state check
 * added in S24 rejects it. The survivor's inbox is dsu.counseling@dickinsonstate.edu:
 * Dickinson State also abbreviates to DSU. Two near-identical strings, one in each Dakota,
 * and the tool told them apart.
 *
 * Every value below is read from the frozen production CSVs, never invented:
 *   data/output/production-s21.csv  — 11 North Dakota rows, incl. dsu.edu high / +1 605…
 *   data/output/production-s24.csv  — 10 North Dakota rows, dsu.edu gone
 * Re-verify with: grep 'North Dakota' data/output/production-s2{1,4}.csv
 *
 * Motion is the pipeline's own work: a check walks the list and takes one out. Everything
 * that animates resolves into a permanent mark, so the reduced-motion end state is the
 * whole story with no frames played.
 */

// Presentational order only — the run's candidate order carries no meaning.
const LINEUP = [
  { domain: 'hhs.nd.gov', org: 'North Dakota Health and Human Services', state: 'ND' },
  { domain: 'und.edu', org: 'University of North Dakota', state: 'ND' },
  { domain: 'ndsu.edu', org: 'North Dakota State University', state: 'ND' },
  { domain: 'bismarckstate.edu', org: 'Bismarck State College', state: 'ND' },
  { domain: 'vcsu.edu', org: 'Valley City State University', state: 'ND' },
  { domain: 'ndscs.edu', org: 'North Dakota State College of Science', state: 'ND' },
  { domain: 'minotstateu.edu', org: 'Minot State University', state: 'ND' },
  { domain: 'dsu.edu', org: 'Dakota State University', state: 'SD' },
  { domain: 'dickinsonstate.edu', org: 'Dickinson State University', state: 'ND' },
  { domain: 'ndus.edu', org: 'North Dakota University System', state: 'ND' },
  { domain: 'umary.edu', org: 'University of Mary', state: 'ND' },
]

const REJECT_INDEX = 7
const SURVIVOR_INDEX = 8

const RAIL = [
  { label: 'Lineup', phase: 1 },
  { label: 'Geography', phase: 2 },
  { label: 'Contact', phase: 4 },
  { label: 'Row', phase: 6 },
]

// Per-phase dwell. The geography beat is long because it carries the rejection.
const BEATS = [300, 900, 1500, 900, 700, 800, 900]
const LAST = BEATS.length - 1

function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

export function CaseFile() {
  const { ref, shown } = useReveal(0.2)
  const [phase, setPhase] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const [jumped, setJumped] = useState(false)
  const timer = useRef<number | null>(null)

  const stop = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
  }, [])

  const play = useCallback(() => {
    stop()
    setJumped(false)
    setPhase(0)
    setPlaying(true)
  }, [stop])

  // Start once on screen. Reduced motion gets the finished state without a chain.
  useEffect(() => {
    if (!shown || phase !== -1) return
    if (prefersReducedMotion()) {
      setPhase(LAST)
      return
    }
    play()
  }, [shown, phase, play])

  // One chained timeout per phase; beats differ, so this is not an interval.
  useEffect(() => {
    if (!playing || phase < 0 || phase >= LAST) return
    timer.current = window.setTimeout(() => {
      setPhase((p) => {
        const next = p + 1
        if (next >= LAST) setPlaying(false)
        return next
      })
    }, BEATS[phase])
    return stop
  }, [playing, phase, stop])

  useEffect(() => stop, [stop])

  const jumpTo = (target: number) => {
    stop()
    setJumped(true)
    setPlaying(false)
    setPhase(target)
  }

  const at = Math.max(phase, 0)
  const done = phase >= LAST && !playing
  const checked = at >= 2

  const rowState = (i: number) => {
    if (at < 2) return 'pending'
    if (i === REJECT_INDEX) return 'reject'
    if (i === SURVIVOR_INDEX && at >= 3) return 'picked'
    return 'ok'
  }

  return (
    <div
      ref={ref}
      className="cf"
      data-phase={at}
      data-jump={jumped ? '1' : undefined}
      data-filled={at >= 3 ? '1' : undefined}
      data-graded={at >= 4 ? '1' : undefined}
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-text">
            See a run
          </span>
          <h2 className="mt-3 max-w-[24ch] text-[28px] font-semibold leading-tight tracking-[-0.015em] text-fg sm:text-[36px]">
            Ten rows from one page. And the one we threw away.
          </h2>
          <p className="mt-3 max-w-[56ch] text-[15px] leading-relaxed text-fg-muted">
            Addiction Hotline published a North Dakota page. Eleven domains reached the last check.
            This is that check.
          </p>
        </div>
        <button
          type="button"
          onClick={play}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-border-strong px-4 py-2 text-[13px] font-medium text-fg transition-colors hover:bg-raised motion-reduce:hidden"
        >
          {done ? <RotateCcw size={14} /> : <Play size={14} />}
          {done ? 'Replay' : 'Play'}
        </button>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-1.5">
        {RAIL.map((stage, n) => {
          const active = at >= stage.phase && (n === RAIL.length - 1 || at < RAIL[n + 1].phase)
          return (
            <button
              key={stage.label}
              type="button"
              onClick={() => jumpTo(stage.phase)}
              aria-current={active ? 'step' : undefined}
              className={`h-6 rounded-full px-2.5 text-[11px] font-medium transition-colors ${
                active
                  ? 'bg-brand-soft text-brand-text'
                  : at > stage.phase
                    ? 'text-fg-muted hover:text-fg'
                    : 'text-fg-subtle hover:text-fg-muted'
              }`}
            >
              <span className="hidden sm:inline">{stage.label}</span>
              <span className="sm:hidden">{n + 1}</span>
            </button>
          )
        })}
      </div>
      <div className="mt-3 h-px w-full bg-border">
        <div
          className="h-px bg-brand transition-[width] duration-500"
          style={{ width: `${(at / LAST) * 100}%` }}
        />
      </div>

      <div className="card cf-card mt-8 overflow-hidden p-0">
        <div className="cf-trigger flex h-12 items-center gap-3 border-b border-border px-4">
          <span className="badge badge-ah font-semibold">AH</span>
          <span
            className="truncate text-[12.5px] text-fg"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            addictionhotline.com/north-dakota/
          </span>
          <span className="ml-auto hidden items-center gap-2 text-[11px] text-fg-subtle sm:flex">
            <span className="live-dot h-1.5 w-1.5 rounded-full bg-brand" aria-hidden />
            new geo page
          </span>
        </div>

        <div className="grid lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
          <div className="cf-lineup relative border-b border-border p-4 lg:border-b-0 lg:border-r">
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <span className="text-[10px] uppercase tracking-[0.14em] text-fg-subtle">
                Domains that reached the check
              </span>
              <span className="shrink-0 text-[11px] text-fg-subtle tnum">
                {checked ? '10 in state · 1 out' : '11 checked'}
              </span>
            </div>

            <span className="cf-sweep" aria-hidden />

            <ol className={`space-y-px ${checked ? 'cf-checked' : ''}`}>
              {LINEUP.map((item, i) => (
                <li
                  key={item.domain}
                  className="cf-row relative flex h-[30px] items-center gap-2 rounded-md pl-2.5 pr-2 text-[11.5px]"
                  data-state={rowState(i)}
                  style={{ ['--i']: i, fontFamily: 'var(--font-mono)' } as CSSProperties}
                  title={item.org}
                >
                  <span
                    className="cf-glyph flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full"
                    aria-hidden
                  >
                    {i === REJECT_INDEX ? (
                      <X size={9} strokeWidth={3} />
                    ) : (
                      <Check size={9} strokeWidth={3} />
                    )}
                  </span>
                  <span className="cf-domain relative truncate">
                    {item.domain}
                    <span className="cf-strike" aria-hidden />
                  </span>
                  <span className="cf-state ml-auto shrink-0 text-[10px] font-semibold tracking-[0.08em]">
                    {item.state}
                  </span>
                  {i === REJECT_INDEX && (
                    <span className="cf-stamp" aria-hidden>
                      South Dakota
                    </span>
                  )}
                </li>
              ))}
            </ol>

            <p className="cf-caption mt-3 min-h-[4.4em] text-[12px] leading-relaxed text-fg-muted">
              <span className="text-fg">dsu.edu is Dakota State University.</span> A real counseling
              centre, a real same-domain inbox, and a 605 phone number. The campus-state check
              rejects it before it reaches your list. It is the other Dakota.
            </p>
          </div>

          <dl className="cf-file">
            <Field label="Subject" n={0}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13.5px] text-fg" style={{ fontFamily: 'var(--font-mono)' }}>
                  dickinsonstate.edu
                </span>
                <span className="badge badge-ah font-semibold">AH</span>
              </div>
              <p className="mt-1 text-[11.5px] text-fg-subtle">promoted from eleven</p>
            </Field>

            <Field label="Page" n={1}>
              <p
                className="break-all text-[12.5px] leading-snug"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                <span className="text-fg-subtle">dickinsonstate.edu</span>
                <span className="text-fg">
                  /student-life/health-and-wellness/counseling-services/
                </span>
              </p>
              <p className="mt-1 text-[11.5px] text-fg-subtle">
                <s>dickinsonstate.edu/</s> not the homepage
              </p>
            </Field>

            <Field label="Contact" n={2}>
              <p className="text-[13.5px] text-fg" style={{ fontFamily: 'var(--font-mono)' }}>
                <span className="cf-echo">dsu.</span>counseling@dickinsonstate.edu
              </p>
              <div
                className="mt-2 flex items-center gap-1"
                role="img"
                aria-label="Contact trust: high"
              >
                {(['low', 'medium', 'high'] as const).map((band, n) => (
                  <span
                    key={band}
                    className={`cf-seg cf-seg-${band}`}
                    style={{ ['--n']: n } as CSSProperties}
                  >
                    {band}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-[11.5px] text-fg-subtle">
                mailto (same-domain) · +1 701 225 4506
              </p>
              <p className="mt-1 text-[11.5px] text-fg-muted">
                Same initials as the domain we rejected. Different school, different state.
              </p>
            </Field>

            <Field label="Competitors" n={3}>
              <div className="flex flex-wrap items-center gap-1.5">
                {['addictions.com', 'drugrehabus.org', 'rehabs.org'].map((domain) => (
                  <span key={domain} className="badge badge-flag">
                    <Flag size={10} />
                    {domain}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-[11.5px] text-fg-muted">
                3 of 16 directories already link here. A warm opening, not a cold one.
              </p>
            </Field>
          </dl>
        </div>

        <div className="cf-out border-t border-border px-4 py-4">
          <div className="mb-2.5 flex items-baseline justify-between gap-3">
            <span className="text-[10px] uppercase tracking-[0.14em] text-fg-subtle">
              Written to the workspace
            </span>
            <span className="text-[12px] text-fg-muted tnum">10 rows from this page</span>
          </div>

          <p
            className="mb-2.5 flex items-center gap-2 text-[12.5px] sm:hidden"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <span className="h-1.5 w-1.5 shrink-0 rounded-full dot-high" />
            <span className="break-all">dsu.counseling@dickinsonstate.edu</span>
          </p>

          <div className="overflow-x-auto">
            <table className="w-full min-w-max border-collapse">
              <caption className="sr-only">
                The finished prospect row for dickinsonstate.edu.
              </caption>
              <thead>
                <tr>
                  {[
                    'Website',
                    'Specific Page',
                    'Email',
                    'Trust',
                    'Geo Served',
                    'Source',
                    'Competitors',
                    'Population',
                    'Confidence',
                  ].map((head) => (
                    <th
                      key={head}
                      className={`border-b border-border bg-raised px-3 py-1.5 text-left text-[10px] uppercase tracking-wide text-fg-subtle ${
                        head === 'Website' || head === 'Trust' || head === 'Competitors'
                          ? ''
                          : 'hidden sm:table-cell'
                      }`}
                    >
                      {head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="text-[12px]">
                  <Cell n={0} className="cf-shipped max-w-[180px] truncate text-fg">
                    dickinsonstate.edu
                  </Cell>
                  <Cell n={1} hide className="max-w-[220px] truncate text-fg-muted">
                    /student-life/health-and-wellness/counseling-services/
                  </Cell>
                  <Cell n={2} hide className="text-fg-muted">
                    dsu.counseling@dickinsonstate.edu
                  </Cell>
                  <Cell n={3}>
                    <span className="badge badge-high">
                      <span className="h-1.5 w-1.5 rounded-full dot-high" />
                      high
                    </span>
                  </Cell>
                  <Cell n={4} hide className="text-fg-muted">
                    North Dakota
                  </Cell>
                  <Cell n={5} hide>
                    <span className="badge badge-ah">AH</span>
                  </Cell>
                  <Cell n={6}>
                    <span className="badge badge-flag">
                      <Flag size={10} />3
                    </span>
                  </Cell>
                  <Cell n={7} hide className="text-right text-fg-muted tnum">
                    784,841
                  </Cell>
                  <Cell n={8} hide className="text-fg-muted">
                    high
                  </Cell>
                </tr>
              </tbody>
            </table>
          </div>

          <p className="mt-2.5 text-[11.5px] text-fg-subtle sm:hidden">
            Page, email, source, population and confidence are in the row too.
          </p>
        </div>
      </div>

      {/* The real scale, and the honest proportion. 589/1754 is 33.58% — never round it up. */}
      <div className="mt-6">
        <div className="flex items-baseline justify-between text-[11.5px]">
          <span className="font-medium" style={{ color: 'var(--high-fg)' }}>
            589 rows written
          </span>
          <span className="text-fg-subtle">1,754 candidates found</span>
        </div>
        <div
          className="mt-2 flex h-2.5 w-full overflow-hidden rounded-full bg-raised"
          role="img"
          aria-label="589 of 1,754 candidates became rows, 33.6 percent"
        >
          <span className="h-full" style={{ width: '33.58%', background: 'var(--high-fg)' }} />
          <span
            className="h-full flex-1"
            style={{ background: 'color-mix(in srgb, var(--low-fg) 30%, transparent)' }}
          />
        </div>
        <p className="mt-2.5 text-[12.5px] leading-relaxed text-fg-subtle">
          Across the production run: 72 geo pages, 637 pages detected, 21 candidates hard-rejected
          for being in the wrong state. 33.6% of what we found is what you get.
        </p>
      </div>
    </div>
  )
}

function Field({ label, n, children }: { label: string; n: number; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[76px_minmax(0,1fr)] items-start gap-4 border-t border-border px-5 py-3.5 first:border-t-0">
      <dt className="pt-0.5 text-[10px] uppercase tracking-[0.14em] text-fg-subtle">{label}</dt>
      <dd className="cf-val min-w-0" style={{ ['--d']: n } as CSSProperties}>
        {children}
      </dd>
    </div>
  )
}

function Cell({
  n,
  hide,
  className = '',
  children,
}: {
  n: number
  hide?: boolean
  className?: string
  children: React.ReactNode
}) {
  return (
    <td
      className={`border-b border-border px-3 py-2 align-middle ${hide ? 'hidden sm:table-cell' : ''}`}
    >
      <span className={`cf-cell block ${className}`} style={{ ['--c']: n } as CSSProperties}>
        {children}
      </span>
    </td>
  )
}
