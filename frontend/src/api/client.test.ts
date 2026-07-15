import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { API, makeProspect, server } from '../test/server'
import { ApiError, getProspects, getStats, patchOutreach, triggerRun } from './client'

describe('api client', () => {
  it('sends filter + pagination params and parses the page', async () => {
    let params: URLSearchParams | null = null
    server.use(
      http.get(`${API}/prospects`, ({ request }) => {
        params = new URL(request.url).searchParams
        return HttpResponse.json({
          items: [makeProspect({ website: 'x.gov' })],
          total: 1,
          limit: 25,
          offset: 50,
        })
      }),
    )
    const page = await getProspects({
      contact_trust: 'high',
      outreach_status: 'contacted',
      limit: 25,
      offset: 50,
    })
    expect(params!.get('contact_trust')).toBe('high')
    expect(params!.get('outreach_status')).toBe('contacted')
    expect(params!.get('limit')).toBe('25')
    expect(params!.get('offset')).toBe('50')
    expect(page.items[0].website).toBe('x.gov')
    expect(page.total).toBe(1)
  })

  it('omits filter params that are not set', async () => {
    let params: URLSearchParams | null = null
    server.use(
      http.get(`${API}/prospects`, ({ request }) => {
        params = new URL(request.url).searchParams
        return HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 })
      }),
    )
    await getProspects({ contact_trust: 'high' })
    expect(params!.has('source_tag')).toBe(false)
    expect(params!.has('outreach_status')).toBe(false)
  })

  it('throws ApiError carrying the status on a non-2xx response', async () => {
    server.use(http.get(`${API}/stats`, () => new HttpResponse(null, { status: 500 })))
    await expect(getStats()).rejects.toBeInstanceOf(ApiError)
    await expect(getStats()).rejects.toMatchObject({ status: 500 })
  })

  it('patchOutreach sends the status + notes body to the right prospect', async () => {
    let body: unknown = null
    let id: string | readonly string[] | undefined
    server.use(
      http.patch(`${API}/prospects/:id/outreach`, async ({ request, params }) => {
        body = await request.clone().json()
        id = params.id
        return HttpResponse.json(makeProspect({ id: 7, outreach_status: 'contacted' }))
      }),
    )
    const p = await patchOutreach(7, { status: 'contacted', notes: 'called the director' })
    expect(id).toBe('7')
    expect(body).toEqual({ status: 'contacted', notes: 'called the director' })
    expect(p.outreach_status).toBe('contacted')
  })

  it('triggerRun POSTs the chosen site + mode and returns the run id', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/runs`, async ({ request }) => {
        body = await request.clone().json()
        return HttpResponse.json({ run_id: 42, status: 'running' })
      }),
    )
    const res = await triggerRun({ site: 'mhd', mode: 'full' })
    expect(body).toEqual({ site: 'mhd', mode: 'full' })
    expect(res.run_id).toBe(42)
  })
})
