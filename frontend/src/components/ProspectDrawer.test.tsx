import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { API, makeProspect, server } from '../test/server'
import { renderWithProviders } from '../test/utils'
import { ProspectDrawer } from './ProspectDrawer'

describe('ProspectDrawer', () => {
  it('renders the selected prospect contact, resource page and competitor chips', () => {
    const p = makeProspect({
      website: 'oc.gov',
      email: 'bh@oc.gov',
      specific_page: 'https://oc.gov/behavioral-health',
      competitor_links: 'samhsa.gov; findtreatment.gov',
      contact_found_on: 'https://county.gov/resources',
    })
    renderWithProviders(<ProspectDrawer prospect={p} onClose={vi.fn()} notify={vi.fn()} />)
    expect(screen.getByText('bh@oc.gov')).toBeInTheDocument()
    expect(screen.getByText('samhsa.gov')).toBeInTheDocument()
    expect(screen.getByText('findtreatment.gov')).toBeInTheDocument()
  })

  it('names the page the competitor links are actually on when it is not the contact page', () => {
    // The client-reported ucr.edu case: the contact page shows no competitor links because the
    // check also covers one resources hop, so a correct row read as a false positive.
    const p = makeProspect({
      specific_page: 'https://counseling.ucr.edu/',
      competitor_links: 'samhsa.gov',
      contact_found_on: 'https://counseling.ucr.edu/resources-support',
    })
    renderWithProviders(<ProspectDrawer prospect={p} onClose={vi.fn()} notify={vi.fn()} />)
    const link = screen.getByRole('link', { name: 'https://counseling.ucr.edu/resources-support' })
    expect(link).toHaveAttribute('href', 'https://counseling.ucr.edu/resources-support')
  })

  it('says nothing about provenance when the links are on the contact page itself', () => {
    const p = makeProspect({ competitor_links: 'samhsa.gov', contact_found_on: '' })
    renderWithProviders(<ProspectDrawer prospect={p} onClose={vi.fn()} notify={vi.fn()} />)
    expect(screen.queryByText(/Found on/)).not.toBeInTheDocument()
  })

  it('copies a contact value to the clipboard', async () => {
    const p = makeProspect({ email: 'bh@oc.gov' })
    renderWithProviders(<ProspectDrawer prospect={p} onClose={vi.fn()} notify={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /copy email/i }))
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('bh@oc.gov')
  })

  it('saves an outreach change with the right PATCH body, updates the pill, and toasts success', async () => {
    const p = makeProspect({ id: 5, outreach_status: 'not_contacted' })
    let body: unknown = null
    server.use(
      http.patch(`${API}/prospects/:id/outreach`, async ({ request }) => {
        body = await request.clone().json()
        return HttpResponse.json(
          makeProspect({
            id: 5,
            outreach_status: 'contacted',
            outreach_notes: 'called the director',
            outreach_updated_by: 'me@dbh.com',
            outreach_updated_at: '2026-07-15T00:00:00Z',
          }),
        )
      }),
    )
    const notify = vi.fn()
    renderWithProviders(<ProspectDrawer prospect={p} onClose={vi.fn()} notify={notify} />)

    await userEvent.selectOptions(screen.getByRole('combobox'), 'contacted')
    await userEvent.type(
      screen.getByPlaceholderText(/notes on the conversation/i),
      'called the director',
    )
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() => expect(body).toEqual({ status: 'contacted', notes: 'called the director' }))
    expect(notify).toHaveBeenCalledWith(expect.objectContaining({ tone: 'success' }))
    await waitFor(() => expect(document.querySelector('.badge-oc-contacted')).toBeInTheDocument())
    expect(await screen.findByRole('button', { name: /saved/i })).toBeInTheDocument()
  })

  it('toasts an error when the save fails', async () => {
    const p = makeProspect({ id: 6 })
    server.use(
      http.patch(`${API}/prospects/:id/outreach`, () => new HttpResponse(null, { status: 500 })),
    )
    const notify = vi.fn()
    renderWithProviders(<ProspectDrawer prospect={p} onClose={vi.fn()} notify={notify} />)
    await userEvent.selectOptions(screen.getByRole('combobox'), 'contacted')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() =>
      expect(notify).toHaveBeenCalledWith(expect.objectContaining({ tone: 'error' })),
    )
  })
})
