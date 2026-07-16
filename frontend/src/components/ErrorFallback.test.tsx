import * as Sentry from '@sentry/react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ErrorFallback } from './ErrorFallback'

function Boom(): never {
  throw new Error('component blew up')
}

describe('ErrorBoundary + fallback', () => {
  it('shows the recovery screen (not a white page) when a child component crashes', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {}) // silence React's caught-error log
    render(
      <Sentry.ErrorBoundary
        fallback={({ resetError }) => <ErrorFallback resetError={resetError} />}
      >
        <Boom />
      </Sentry.ErrorBoundary>,
    )
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reload the app/i })).toBeInTheDocument()
  })

  it('calls resetError when the reload button is clicked', async () => {
    const reset = vi.fn()
    render(<ErrorFallback resetError={reset} />)
    await userEvent.click(screen.getByRole('button', { name: /reload the app/i }))
    expect(reset).toHaveBeenCalledOnce()
  })
})
