import * as Sentry from '@sentry/react'
import type { ErrorEvent } from '@sentry/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { initMonitoring } from './monitoring'

vi.mock('@sentry/react', () => ({ init: vi.fn() }))
const initMock = vi.mocked(Sentry.init)

afterEach(() => {
  vi.unstubAllEnvs()
  initMock.mockClear()
})

describe('frontend monitoring', () => {
  it('is disabled (silent) when no DSN is configured', () => {
    expect(initMonitoring()).toBe(false)
    expect(initMock).not.toHaveBeenCalled()
  })

  it('enables and its beforeSend redacts emails + drops cookies', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://k@example.ingest.sentry.io/1')

    expect(initMonitoring()).toBe(true)

    const beforeSend = initMock.mock.calls[0]?.[0]?.beforeSend
    expect(beforeSend).toBeTypeOf('function')
    const event = {
      message: 'could not reach bh@oc.gov',
      exception: { values: [{ value: 'director@county.gov is invalid' }] },
      request: { cookies: { session: 'secret' } },
    } as unknown as ErrorEvent
    const out = beforeSend?.(event, {}) as ErrorEvent

    expect(out.message).not.toContain('bh@oc.gov')
    expect(out.message).toContain('[email]')
    expect(out.exception?.values?.[0]?.value).toContain('[email]')
    expect(out.request?.cookies).toBeUndefined()
  })
})
