import { Check, Play, RotateCcw, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useReveal } from '../../lib/useReveal'

/**
 * A real run, traced. One geo page from Addiction Hotline goes through every stage of the
 * pipeline and comes out as a prospect the team can email.
 *
 * The geo, the candidates, the rejection, and the finished row are all real: uwyo.edu is a
 * live Wyoming prospect in the dataset, and cornell.edu under Wyoming is a real wrong-state
 * rejection from the ADR-024 audit. It plays on its own when scrolled to, and can be replayed.
 */

interface Stage {
  label: string
  detail: string
  lines: { text: string; tone?: 'ok' | 'reject' | 'muted' }[]
}

const STAGES: Stage[] = [
  {
    label: 'New geo page',
    detail: 'The sitemap poll finds a page that was not there yesterday.',
    lines: [
      { text: 'addictionhotline.com/wyoming/', tone: 'ok' },
      { text: 'state level, first seen today', tone: 'muted' },
    ],
  },
  {
    label: 'Search the geography',
    detail: 'Targeted queries for that state, .gov and .edu only.',
    lines: [
      { text: 'uwyo.edu' },
      { text: 'sheridan.edu' },
      { text: 'health.wyo.gov' },
      { text: 'cornell.edu' },
    ],
  },
  {
    label: 'Prove the geography',
    detail: 'Anything belonging to another state is dropped here, not later.',
    lines: [
      { text: 'uwyo.edu is Wyoming', tone: 'ok' },
      { text: 'sheridan.edu is Wyoming', tone: 'ok' },
      { text: 'cornell.edu is New York, rejected', tone: 'reject' },
    ],
  },
  {
    label: 'Find the department page',
    detail: 'The counseling page, not the university homepage.',
    lines: [
      { text: 'uwyo.edu/ucc/index.html', tone: 'ok' },
      { text: 'University Counseling Center', tone: 'muted' },
    ],
  },
  {
    label: 'Pull the contact',
    detail: 'A same-domain inbox, then graded for how safe it is to mail.',
    lines: [
      { text: 'uccstaff@uwyo.edu', tone: 'ok' },
      { text: '+1 307 766 1121', tone: 'muted' },
    ],
  },
  {
    label: 'Row ready',
    detail: 'Written to the workspace and the sheet, deduplicated by site and geo.',
    lines: [{ text: 'uwyo.edu added under Wyoming', tone: 'ok' }],
  },
]

const STEP_MS = 1500

export function PipelineTrace() {
  const { ref, shown } = useReveal(0.25)
  const [step, setStep] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const timer = useRef<number | null>(null)

  const stop = useCallback(() => {
    if (timer.current !== null) window.clearInterval(timer.current)
    timer.current = null
  }, [])

  const play = useCallback(() => {
    stop()
    setStep(0)
    setPlaying(true)
    timer.current = window.setInterval(() => {
      setStep((current) => {
        if (current >= STAGES.length - 1) {
          stop()
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, STEP_MS)
  }, [stop])

  // Start once the trace is actually on screen, and never run in the background.
  useEffect(() => {
    if (!shown || step !== -1) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setStep(STAGES.length - 1) // show the finished trace instead of animating it
      return
    }
    play()
  }, [shown, step, play])

  useEffect(() => stop, [stop])

  const done = step >= STAGES.length - 1 && !playing

  return (
    <div ref={ref}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="max-w-[20ch] text-[28px] font-semibold leading-tight tracking-[-0.015em] text-fg sm:text-[36px]">
            One page in, one prospect out.
          </h2>
          <p className="mt-3 max-w-[54ch] text-[15px] leading-relaxed text-fg-muted">
            A real run on a Wyoming page from Addiction Hotline, stage by stage.
          </p>
        </div>
        <button
          type="button"
          onClick={play}
          className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-border-strong px-4 py-2 text-[13px] font-medium text-fg transition-colors hover:bg-raised"
        >
          {done ? <RotateCcw size={14} /> : <Play size={14} />}
          {done ? 'Replay' : 'Play'}
        </button>
      </div>

      <ol className="mt-10 grid gap-3 lg:grid-cols-3">
        {STAGES.map((stage, i) => {
          const active = i === step
          const complete = i < step
          const reached = i <= step
          return (
            <li
              key={stage.label}
              aria-current={active ? 'step' : undefined}
              className={`card p-5 transition-all duration-500 ${
                reached ? 'opacity-100' : 'opacity-35'
              } ${active ? 'border-brand/50' : ''}`}
              style={
                active
                  ? { boxShadow: '0 0 0 1px var(--brand-soft), var(--shadow-lift)' }
                  : undefined
              }
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold transition-colors ${
                    complete
                      ? 'bg-brand text-brand-fg'
                      : active
                        ? 'bg-brand-soft text-brand'
                        : 'bg-raised text-fg-subtle'
                  }`}
                >
                  {complete ? <Check size={13} strokeWidth={2.6} /> : i + 1}
                </span>
                <h3 className="text-[14px] font-semibold text-fg">{stage.label}</h3>
              </div>
              <p className="mt-2.5 min-h-[2.6em] text-[12.5px] leading-relaxed text-fg-muted">
                {stage.detail}
              </p>
              <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
                {stage.lines.map((line) => (
                  <li
                    key={line.text}
                    className={`flex items-start gap-1.5 text-[11.5px] leading-snug transition-opacity duration-500 ${
                      reached ? 'opacity-100' : 'opacity-0'
                    }`}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      color:
                        line.tone === 'ok'
                          ? 'var(--high-fg)'
                          : line.tone === 'reject'
                            ? 'var(--flag-fg)'
                            : 'var(--fg-subtle)',
                    }}
                  >
                    {line.tone === 'reject' ? (
                      <X size={12} className="mt-px shrink-0" />
                    ) : line.tone === 'ok' ? (
                      <Check size={12} className="mt-px shrink-0" />
                    ) : null}
                    <span className="break-all">{line.text}</span>
                  </li>
                ))}
              </ul>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
