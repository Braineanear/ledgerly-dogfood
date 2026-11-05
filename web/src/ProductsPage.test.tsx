import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ProductsPage from './ProductsPage'

const BASE = 'http://api.test'

function jsonResponse(body: unknown, status = 200, statusText = '') {
  return new Response(JSON.stringify(body), {
    status,
    statusText,
    headers: { 'Content-Type': 'application/json' },
  })
}

function submit(tenantId: string) {
  fireEvent.change(screen.getByLabelText('Tenant id'), {
    target: { value: tenantId },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Load' }))
}

describe('ProductsPage', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', BASE)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('shows a loading status while the request is pending', async () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    render(<ProductsPage />)

    submit('7')

    expect(await screen.findByRole('status')).toBeInTheDocument()
  })

  it('lists products and sends no Authorization header', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        items: [
          { id: 1, sku: 'A-1', name: 'Widget', price: 1250, currency: 'USD' },
          { id: 2, sku: 'B-2', name: 'Gadget', price: null, currency: null },
        ],
        next_cursor: null,
      }),
    )
    render(<ProductsPage />)

    submit('7')

    expect(await screen.findByText(/A-1 - Widget - \$12\.50/)).toBeVisible()
    expect(screen.getByText(/B-2 - Gadget - -/)).toBeVisible()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${BASE}/tenants/7/products`)
    expect(new Headers(init?.headers).has('Authorization')).toBe(false)
  })

  it.each([
    [401, 'Unauthorized', 'Invalid token', '401: Invalid token'],
    [500, 'Server Error', 'Boom', '500: Boom'],
  ])('shows an alert for a %i problem response', async (
    status,
    title,
    detail,
    message,
  ) => {
    fetchMock.mockResolvedValue(jsonResponse({ title, detail }, status))
    render(<ProductsPage />)

    submit('7')

    expect(await screen.findByRole('alert')).toHaveTextContent(message)
  })

  it('shows an alert when the request rejects', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    render(<ProductsPage />)

    submit('7')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Failed to fetch',
    )
  })

  it('shows a message for an empty list', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ items: [], next_cursor: null }))
    render(<ProductsPage />)

    submit('7')

    expect(await screen.findByText('No products found.')).toBeVisible()
  })

  it('notes that only the first page is shown', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        items: [
          { id: 1, sku: 'A-1', name: 'Widget', price: 100, currency: 'USD' },
        ],
        next_cursor: 'abc',
      }),
    )
    render(<ProductsPage />)

    submit('7')

    expect(
      await screen.findByText('Only the first page of products is shown.'),
    ).toBeVisible()
  })

  it('does not fetch for an empty tenant id', async () => {
    render(<ProductsPage />)

    submit('  ')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Enter a tenant id.',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
