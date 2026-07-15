import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import App from './App'
import { API, authUser, server } from './test/server'
import { renderWithProviders } from './test/utils'

describe('auth gate', () => {
  it('shows the login screen when the session check returns 401', async () => {
    server.use(http.get(`${API}/auth/me`, () => new HttpResponse(null, { status: 401 })))
    renderWithProviders(<App />)
    expect(
      await screen.findByText(/sign in to access your outreach prospects/i),
    ).toBeInTheDocument()
  })

  it('renders the app shell + prospect rows when authenticated', async () => {
    renderWithProviders(<App />)
    // a prospect row from the default handler proves the authed app rendered
    expect(await screen.findByText('a.gov')).toBeInTheDocument()
    expect(screen.queryByText(/sign in to access your outreach prospects/i)).not.toBeInTheDocument()
  })

  it('returns to the login screen after logout', async () => {
    let loggedIn = true
    server.use(
      http.get(`${API}/auth/me`, () =>
        loggedIn ? HttpResponse.json(authUser) : new HttpResponse(null, { status: 401 }),
      ),
      http.post(`${API}/auth/logout`, () => {
        loggedIn = false
        return HttpResponse.json({ ok: true })
      }),
    )
    renderWithProviders(<App />)
    const logout = await screen.findByRole('button', { name: /sign out/i })
    await userEvent.click(logout)
    expect(
      await screen.findByText(/sign in to access your outreach prospects/i),
    ).toBeInTheDocument()
  })
})
