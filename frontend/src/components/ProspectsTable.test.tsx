import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { makeProspect } from '../test/server'
import { ProspectsTable } from './ProspectsTable'

const rows = [
  makeProspect({ id: 1, website: 'low.gov', contact_trust: 'low', population: 100 }),
  makeProspect({ id: 2, website: 'high.gov', contact_trust: 'high', population: 900 }),
  makeProspect({ id: 3, website: 'med.gov', contact_trust: 'medium', population: 500 }),
]

function websitesInOrder(): string[] {
  return [...document.querySelectorAll('tbody tr')].map(
    (r) => r.querySelector('td')?.textContent?.trim() ?? '',
  )
}

describe('ProspectsTable', () => {
  it('renders a row per prospect plus the header row', () => {
    render(<ProspectsTable prospects={rows} selectedId={null} onSelect={vi.fn()} />)
    expect(screen.getByText('high.gov')).toBeInTheDocument()
    expect(screen.getByText('low.gov')).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(rows.length + 1)
  })

  it('sorts by trust ascending then descending when the Trust header is clicked', async () => {
    render(<ProspectsTable prospects={rows} selectedId={null} onSelect={vi.fn()} />)
    const trustHeader = screen.getByRole('button', { name: /^trust$/i })
    await userEvent.click(trustHeader)
    expect(websitesInOrder()).toEqual(['low.gov', 'med.gov', 'high.gov'])
    await userEvent.click(trustHeader)
    expect(websitesInOrder()).toEqual(['high.gov', 'med.gov', 'low.gov'])
  })

  it('hides a column through the Columns menu', async () => {
    render(<ProspectsTable prospects={rows} selectedId={null} onSelect={vi.fn()} />)
    expect(screen.getByRole('columnheader', { name: /email/i })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /columns/i }))
    await userEvent.click(screen.getByRole('checkbox', { name: /email/i }))
    expect(screen.queryByRole('columnheader', { name: /email/i })).not.toBeInTheDocument()
  })

  it('calls onSelect with the clicked prospect', async () => {
    const onSelect = vi.fn()
    render(<ProspectsTable prospects={rows} selectedId={null} onSelect={onSelect} />)
    await userEvent.click(screen.getByText('high.gov'))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ website: 'high.gov' }))
  })
})
