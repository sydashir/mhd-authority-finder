// AuthorityScout logomark — a radar / scope: concentric rings, crosshair ticks,
// a sweep line to a blip. Single-color (currentColor), crisp at small sizes.
export function Logo({ size = 22, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      className={className}
      aria-hidden
    >
      <circle cx="12" cy="12" r="9.25" />
      <circle cx="12" cy="12" r="5" opacity="0.55" />
      <path d="M12 1.5v2.4M12 20.1v2.4M1.5 12h2.4M20.1 12h2.4" opacity="0.7" />
      <path d="M12 12 18.4 6.6" />
      <circle cx="18.4" cy="6.6" r="1.5" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.15" fill="currentColor" stroke="none" />
    </svg>
  )
}
