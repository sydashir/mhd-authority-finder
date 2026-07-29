/**
 * The hero visual: a radar sweeping a geography and lighting up the authority sites it
 * finds. It is the product's actual job in one image, and it extends the logomark
 * (a scope) rather than decorating around it.
 *
 * Every blip is a real domain from the live dataset. The sweep is one CSS rotation on a
 * gradient wedge; each blip pulses on the beat the sweep passes it, so the motion reads
 * as cause and effect instead of ambient shimmer. Static under reduced motion.
 */

// Real prospects, placed by angle so the sweep meets them in sequence.
const BLIPS = [
  { label: 'ucr.edu', angle: 18, radius: 0.74, trust: 'high' },
  { label: 'pinellas.gov', angle: 68, radius: 0.5, trust: 'high' },
  { label: 'tamut.edu', angle: 124, radius: 0.82, trust: 'high' },
  { label: 'nau.edu', angle: 176, radius: 0.42, trust: 'medium' },
  { label: 'astate.edu', angle: 222, radius: 0.68, trust: 'high' },
  { label: 'goyff.az.gov', angle: 288, radius: 0.56, trust: 'medium' },
  { label: 'alaska.edu', angle: 332, radius: 0.86, trust: 'high' },
] as const

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
            <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.22" />
            <stop offset="55%" stopColor="var(--brand)" stopOpacity="0.10" />
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
            strokeOpacity="0.8"
            strokeWidth="1.5"
          />
        </g>

        {BLIPS.map((blip) => {
          const { x, y } = polar(blip.angle, blip.radius)
          // Pulse exactly when the sweep line reaches this bearing.
          const delay = `${(blip.angle / 360) * SWEEP_SECONDS}s`
          const anchorRight = blip.angle > 180
          return (
            <g key={blip.label} className="radar-blip" style={{ animationDelay: delay }}>
              <circle
                cx={x}
                cy={y}
                r="9"
                fill="var(--brand)"
                opacity="0.16"
                className="radar-blip-halo"
                style={{ animationDelay: delay }}
              />
              <circle
                cx={x}
                cy={y}
                r="3.2"
                fill={blip.trust === 'high' ? 'var(--brand)' : 'var(--fg-subtle)'}
              />
              <text
                x={anchorRight ? x - 13 : x + 13}
                y={y + 3.5}
                textAnchor={anchorRight ? 'end' : 'start'}
                className="hidden fill-fg-muted text-[10.5px] sm:inline" /* labels would clip at phone widths */
                style={{ fontFamily: 'var(--font-mono)' }}
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
