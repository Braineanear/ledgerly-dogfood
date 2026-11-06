import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import HomePage from './HomePage'

describe('HomePage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the Ledgerly heading', () => {
    render(<HomePage />)

    expect(
      screen.getByRole('heading', { name: 'Ledgerly' }),
    ).toBeInTheDocument()
  })

  it('keeps the products page available on the home page', () => {
    render(<HomePage />)

    expect(screen.getByRole('heading', { name: 'Products' })).toBeVisible()
    expect(screen.getByLabelText('Tenant id')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Load' })).toBeVisible()
  })

  it('loads products when the home page form is submitted', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              id: 1,
              sku: 'A-1',
              name: 'Widget',
              price: 1250,
              currency: 'USD',
            },
          ],
          next_cursor: null,
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<HomePage />)
    fireEvent.change(screen.getByLabelText('Tenant id'), {
      target: { value: '7' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Load' }))

    expect(await screen.findByText(/A-1 - Widget - \$12\.50/)).toBeVisible()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

