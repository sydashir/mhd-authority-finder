import { useEffect, useRef, useState } from 'react'

/**
 * Reveal-on-scroll via IntersectionObserver (never a scroll listener, which would run
 * on every frame). Returns a ref to attach and whether the element has entered once.
 * Under prefers-reduced-motion it reports visible immediately, so nothing is hidden
 * from a user who has asked for stillness.
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>(amount = 0.08) {
  const ref = useRef<T>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    // Degrade to visible when the observer is unavailable (jsdom, older browsers) or the
    // user asked for reduced motion. Content must never be hidden by a missing API.
    if (
      typeof IntersectionObserver === 'undefined' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      setShown(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          // Reveal on entry, and ALSO if the section is already above the viewport: a fast
          // scroll or a jump to an anchor can skip the intersection entirely, and a section
          // that silently stays invisible is worse than one that never animated.
          if (entry.isIntersecting || entry.boundingClientRect.top < 0) {
            setShown(true)
            observer.disconnect() // reveal once, then stop observing
          }
        }
      },
      // A little rootMargin so a section is already settling in as it enters, rather than
      // visibly popping once it is fully on screen.
      { threshold: amount, rootMargin: '0px 0px -8% 0px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [amount])

  return { ref, shown }
}
