// Optional Sentry error monitoring (ADR-023). Enabled ONLY when VITE_SENTRY_DSN is set, so
// local dev is silent (no DSN -> init never runs). Errors only, no tracing/replay (free-tier
// friendly). beforeSend redacts prospect emails and drops cookies before anything is sent.

import * as Sentry from '@sentry/react'

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g

export function initMonitoring(): boolean {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return false
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0, // errors only — no performance spans, no session replay
    beforeSend(event) {
      if (event.message) event.message = event.message.replace(EMAIL_RE, '[email]')
      for (const value of event.exception?.values ?? []) {
        if (value.value) value.value = value.value.replace(EMAIL_RE, '[email]')
      }
      if (event.request?.cookies) delete event.request.cookies
      return event
    },
  })
  return true
}
