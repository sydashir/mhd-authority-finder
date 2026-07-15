import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { API, makeProspect, server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { ProspectsScreen } from './ProspectsScreen'

describe('ProspectsScreen', () => {
  it('sends the selected trust filter to the API and renders only the filtered rows', async () => {
    let lastTrust: string | null = 'UNSET'
    server.use(
      http.get(`${API}/prospects`, ({ request }) => {
        lastTrust = new URL(request.url).searchParams.get('contact_trust')
        const items =
          lastTrust === 'high'
            ? [makeProspect({ website: 'only-high.gov', contact_trust: 'high' })]
            : [makeProspect({ website: 'a.gov' }), makeProspect({ id: 2, website: 'b.gov' })]
        return HttpResponse.json({ items, total: items.length, limit: 50, offset: 0 })
      }),
    )
    renderWithProviders(<ProspectsScreen notify={vi.fn()} />)
    expect(await screen.findByText('a.gov')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText(/trust/i), 'high')

    expect(await screen.findByText('only-high.gov')).toBeInTheDocument()
    expect(lastTrust).toBe('high')
    expect(screen.queryByText('a.gov')).not.toBeInTheDocument()
  })

  it('renders the empty state when no prospects match', async () => {
    server.use(
      http.get(`${API}/prospects`, () =>
        HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
      ),
    )
    renderWithProviders(<ProspectsScreen notify={vi.fn()} />)
    expect(await screen.findByText(/no prospects match/i)).toBeInTheDocument()
  })

  it('renders the error state (with the status) when the API fails', async () => {
    server.use(http.get(`${API}/prospects`, () => new HttpResponse(null, { status: 500 })))
    renderWithProviders(<ProspectsScreen notify={vi.fn()} />)
    expect(await screen.findByText(/couldn.t load prospects/i)).toBeInTheDocument()
    expect(screen.getByText(/returned 500/i)).toBeInTheDocument()
  })
})
