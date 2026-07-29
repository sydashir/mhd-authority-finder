/**
 * The hero visual: a radar sweeping a geography and lighting up the authority sites it
 * finds. It is the product's actual job in one image, and it extends the logomark
 * (a scope) rather than decorating around it.
 *
 * Each blip ignites on the beat the sweep line crosses its bearing and then settles, so the
 * motion reads as cause and effect rather than ambient shimmer. Two of the blips are real
 * wrong-state rejections from the ADR-024 audit and ignite in rose with their domain struck
 * through: the tool's most valuable behaviour is the row it refuses to write, so the hero
 * shows a rejection rather than pretending everything found is a win.
 *
 * Delays are negative so every blip is already mid-cycle at t=0 — a positive delay would
 * leave them unstyled (and wrongly bright) until their first pass came round.
 */

// Real prospects and real rejections, placed by angle so the sweep meets them in sequence.
const BLIPS = [
  { label: 'ucr.edu', angle: 18, radius: 0.74, kind: 'high' },
  { label: 'pinellas.gov', angle: 62, radius: 0.5, kind: 'high' },
  { label: 'cornell.edu', angle: 105, radius: 0.86, kind: 'rejected' },
  { label: 'tamut.edu', angle: 145, radius: 0.66, kind: 'high' },
  { label: 'nau.edu', angle: 186, radius: 0.44, kind: 'medium' },
  { label: 'astate.edu', angle: 228, radius: 0.72, kind: 'high' },
  { label: 'iup.edu', angle: 272, radius: 0.56, kind: 'rejected' },
  { label: 'alaska.edu', angle: 322, radius: 0.84, kind: 'high' },
] as const

const TONE = {
  high: 'var(--brand)',
  medium: 'var(--med-fg)',
  rejected: 'var(--flag-fg)',
} as const

const SIZE = 420
const CENTER = SIZE / 2
const EDGE = 186
const SWEEP_SECONDS = 8

function polar(angle: number, radius: number) {
  const radians = ((angle - 90) * Math.PI) / 180
  return {
    x: CENTER + Math.cos(radians) * EDGE * radius,
    y: CENTER + Math.sin(radians) * EDGE * radius,
  }
}

export function RadarScan() {
  return (
    <div className="relative mx-auto w-full max-w-[420px]" aria-hidden>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-auto w-full overflow-visible">
        <defs>
          <radialGradient id="scope-fill" cx="50%" cy="50%">
            <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.10" />
            <stop offset="70%" stopColor="var(--brand)" stopOpacity="0.03" />
            <stop offset="100%" stopColor="var(--brand)" stopOpacity="0" />
          </radialGradient>
          {/* Anchored at the centre so the trail fades with distance AND behind the line. */}
          <radialGradient id="sweep-fill" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.26" />
            <stop offset="55%" stopColor="var(--brand)" stopOpacity="0.12" />
            <stop offset="100%" stopColor="var(--brand)" stopOpacity="0.01" />
          </radialGradient>
        </defs>

        <circle cx={CENTER} cy={CENTER} r={EDGE} fill="url(#scope-fill)" />
        {[0.32, 0.58, 0.82, 1].map((step) => (
          <circle
            key={step}
            cx={CENTER}
            cy={CENTER}
            r={EDGE * step}
            fill="none"
            stroke="var(--border-strong)"
            strokeOpacity={step === 1 ? 0.9 : 0.45}
            strokeWidth="1"
          />
        ))}
        <path
          d={`M${CENTER - EDGE} ${CENTER}H${CENTER + EDGE}M${CENTER} ${CENTER - EDGE}V${CENTER + EDGE}`}
          stroke="var(--border-strong)"
          strokeOpacity="0.4"
          strokeWidth="1"
        />

        {/* The sweep: one wedge, rotated forever about the centre. */}
        <g className="radar-sweep" style={{ transformOrigin: `${CENTER}px ${CENTER}px` }}>
          <path
            d={`M${CENTER} ${CENTER} L${CENTER} ${CENTER - EDGE} A${EDGE} ${EDGE} 0 0 0 ${CENTER - EDGE * 0.66} ${CENTER - EDGE * 0.75} Z`}
            fill="url(#sweep-fill)"
          />
          <line
            x1={CENTER}
            y1={CENTER}
            x2={CENTER}
            y2={CENTER - EDGE}
            stroke="var(--brand)"
            strokeWidth="1.5"
          />
        </g>

        {BLIPS.map((blip) => {
          const { x, y } = polar(blip.angle, blip.radius)
          // Negative so the cycle is already running; lands on 0% exactly as the line arrives.
          const delay = `${(blip.angle / 360) * SWEEP_SECONDS - SWEEP_SECONDS}s`
          const anchorRight = blip.angle > 180
          const tone = TONE[blip.kind]
          const rejected = blip.kind === 'rejected'
          return (
            <g key={blip.label}>
              <circle
                cx={x}
                cy={y}
                r="4"
                fill="none"
                stroke={tone}
                strokeWidth="1.5"
                className="radar-blip-ring"
                style={{ animationDelay: delay }}
              />
              <circle
                cx={x}
                cy={y}
                r="3.4"
                fill={tone}
                className="radar-blip-dot"
                style={{ animationDelay: delay }}
              />
              {rejected && (
                <path
                  d={`M${x - 2.1} ${y - 2.1}l4.2 4.2M${x + 2.1} ${y - 2.1}l-4.2 4.2`}
                  stroke="var(--app)"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
              )}
              <text
                x={anchorRight ? x - 13 : x + 13}
                y={y + 3.5}
                textAnchor={anchorRight ? 'end' : 'start'}
                fill={tone}
                textDecoration={rejected ? 'line-through' : undefined}
                className="radar-blip-label hidden text-[10.5px] sm:inline" /* labels clip at phone widths */
                style={{ fontFamily: 'var(--font-mono)', animationDelay: delay }}
              >
                {blip.label}
              </text>
            </g>
          )
        })}

        <circle cx={CENTER} cy={CENTER} r="3" fill="var(--brand)" />
      </svg>
    </div>
  )
}
