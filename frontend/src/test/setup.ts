import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { server } from './server'

// MSW lifecycle. `error` on unhandled so a forgotten mock fails loudly, not silently.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  cleanup()
})
afterAll(() => server.close())

// jsdom gaps the components rely on.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  // Report reduced-motion in tests: components then render their final state instead of
  // running timers/animations, which keeps assertions deterministic rather than racing them.
  value: (query: string) => ({
    matches: query.includes('prefers-reduced-motion'),
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
})

Element.prototype.scrollIntoView = vi.fn()

Object.assign(navigator, {
  clipboard: { writeText: vi.fn(() => Promise.resolve()) },
})
