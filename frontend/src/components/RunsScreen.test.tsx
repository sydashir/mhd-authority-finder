import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { API, makeRun, server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { RunNowButton } from './RunNowButton'
import { RunsScreen } from './RunsScreen'

describe('RunsScreen', () => {
  it('renders run rows with site, status badge and counts', async () => {
    server.use(
      http.get(`${API}/runs`, () =>
        HttpResponse.json({
          items: [makeRun({ id: 1, site: 'ah', status: 'success', rows_written: 87 })],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      ),
    )
    renderWithProviders(<RunsScreen notify={vi.fn()} />)
    expect(await screen.findByText(/success/i)).toBeInTheDocument()
    expect(screen.getByText('AH')).toBeInTheDocument()
    expect(screen.getByText('87')).toBeInTheDocument()
  })

  it('shows the empty state when there are no runs', async () => {
    server.use(
      http.get(`${API}/runs`, () => HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 })),
    )
    renderWithProviders(<RunsScreen notify={vi.fn()} />)
    expect(await screen.findByText(/no runs yet/i)).toBeInTheDocument()
  })
})

describe('RunNowButton', () => {
  it('triggers a run with the chosen site + mode and toasts success', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/runs`, async ({ request }) => {
        body = await request.clone().json()
        return HttpResponse.json({ run_id: 42, status: 'running' })
      }),
    )
    const notify = vi.fn()
    renderWithProviders(<RunNowButton notify={notify} />)

    await userEvent.click(screen.getByRole('button', { name: /run now/i }))
    await userEvent.click(screen.getByRole('button', { name: /^MHD$/i }))
    await userEvent.click(screen.getByRole('button', { name: /full re-scan/i }))
    await userEvent.click(screen.getByRole('button', { name: /start run/i }))

    await waitFor(() => expect(body).toEqual({ site: 'mhd', mode: 'full' }))
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ tone: 'success' }))
  })

  it('toasts an error when the trigger fails', async () => {
    server.use(http.post(`${API}/runs`, () => new HttpResponse(null, { status: 500 })))
    const notify = vi.fn()
    renderWithProviders(<RunNowButton notify={notify} />)
    await userEvent.click(screen.getByRole('button', { name: /run now/i }))
    await userEvent.click(screen.getByRole('button', { name: /start run/i }))
    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith(expect.objectContaining({ tone: 'error' })),
    )
  })
})
