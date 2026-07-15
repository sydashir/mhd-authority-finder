import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { API, authUser, server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { Login } from './Login'

// The real Google button is a GSI iframe that can't be driven in jsdom — stand in a plain
// button that fires onSuccess, so the component's real credential-handling logic runs.
vi.mock('@react-oauth/google', () => ({
  GoogleOAuthProvider: ({ children }: { children: ReactNode }) => children,
  GoogleLogin: ({ onSuccess }: { onSuccess: (r: { credential: string }) => void }) => (
    <button type="button" onClick={() => onSuccess({ credential: 'fake-token' })}>
      Sign in with Google
    </button>
  ),
}))

describe('Login', () => {
  it('shows a clear not-authorized message when the account is off the allowlist (403)', async () => {
    server.use(http.post(`${API}/auth/google`, () => new HttpResponse(null, { status: 403 })))
    renderWithProviders(<Login />)
    await userEvent.click(screen.getByRole('button', { name: /sign in with google/i }))
    expect(await screen.findByText(/isn.t authorized/i)).toBeInTheDocument()
  })

  it('shows a generic failure message on a non-403 error', async () => {
    server.use(http.post(`${API}/auth/google`, () => new HttpResponse(null, { status: 500 })))
    renderWithProviders(<Login />)
    await userEvent.click(screen.getByRole('button', { name: /sign in with google/i }))
    expect(await screen.findByText(/sign-in failed/i)).toBeInTheDocument()
  })

  it('succeeds when the credential is accepted', async () => {
    server.use(http.post(`${API}/auth/google`, () => HttpResponse.json(authUser)))
    renderWithProviders(<Login />)
    await userEvent.click(screen.getByRole('button', { name: /sign in with google/i }))
    // no error surfaced (the footer's "authorized team members" is not an error)
    expect(screen.queryByText(/isn.t authorized/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/sign-in failed/i)).not.toBeInTheDocument()
  })
})
