import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import App from './App'
import { API, authUser, server } from './test/server'
import { renderWithProviders } from './test/utils'

const HERO = /local authority sites, ready to contact/i

/** Open the landing page's sign-in dialog and submit credentials. The page has several
 *  "Sign in" buttons (nav, hero, closing CTA), so the submit is scoped to the dialog. */
async function signIn(username: string, password: string) {
  await userEvent.click((await screen.findAllByRole('button', { name: /^sign in$/i }))[0]!)
  const dialog = within(await screen.findByRole('dialog'))
  await userEvent.type(dialog.getByLabelText(/^username$/i), username)
  await userEvent.type(dialog.getByLabelText(/^password$/i), password)
  await userEvent.click(dialog.getByRole('button', { name: /^sign in$/i }))
}

describe('auth gate', () => {
  it('shows the public landing page when the session check returns 401', async () => {
    server.use(http.get(`${API}/auth/me`, () => new HttpResponse(null, { status: 401 })))
    renderWithProviders(<App />)
    expect(await screen.findByRole('heading', { name: HERO })).toBeInTheDocument()
  })

  it('renders the app shell + prospect rows when authenticated', async () => {
    renderWithProviders(<App />)
    // a prospect row from the default handler proves the authed app rendered
    expect(await screen.findByText('a.gov')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: HERO })).not.toBeInTheDocument()
  })

  it('returns to the landing page after logout', async () => {
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
    expect(await screen.findByRole('heading', { name: HERO })).toBeInTheDocument()
  })
})

describe('sign in', () => {
  it('signs in with a username and password and lands in the workspace', async () => {
    let loggedIn = false
    let sent: unknown = null
    server.use(
      http.get(`${API}/auth/me`, () =>
        loggedIn ? HttpResponse.json(authUser) : new HttpResponse(null, { status: 401 }),
      ),
      http.post(`${API}/auth/login`, async ({ request }) => {
        sent = await request.clone().json()
        loggedIn = true
        return HttpResponse.json(authUser)
      }),
    )
    renderWithProviders(<App />)
    await signIn('admin', 'adminuser123')

    await waitFor(() => expect(sent).toEqual({ username: 'admin', password: 'adminuser123' }))
    // the gate flips: the workspace renders a real prospect row
    expect(await screen.findByText('a.gov')).toBeInTheDocument()
  })

  it('shows the API message when the credentials are rejected', async () => {
    server.use(
      http.get(`${API}/auth/me`, () => new HttpResponse(null, { status: 401 })),
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ detail: 'Incorrect username or password.' }, { status: 401 }),
      ),
    )
    renderWithProviders(<App />)
    await signIn('admin', 'wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect username or password/i)
  })

  it('surfaces the lockout message after too many failures', async () => {
    server.use(
      http.get(`${API}/auth/me`, () => new HttpResponse(null, { status: 401 })),
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json(
          { detail: 'Too many failed attempts. Try again in 15 minutes.' },
          { status: 429 },
        ),
      ),
    )
    renderWithProviders(<App />)
    await signIn('admin', 'whatever')

    expect(await screen.findByRole('alert')).toHaveTextContent(/too many failed attempts/i)
  })
})
