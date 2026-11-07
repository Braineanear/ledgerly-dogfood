import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ProductsPage from '../ProductsPage'
import { formatPrice } from '../price'
import I18nProvider from './I18nProvider'
import LocaleSwitcher from './LocaleSwitcher'
import { useI18n } from './context'
import { CATALOGS, STORAGE_KEY, dirFor, translate } from './messages'

function Probe() {
  const { locale, t } = useI18n()
  return (
    <p>
      {locale}:{t('products')}
    </p>
  )
}

function renderApp() {
  return render(
    <I18nProvider>
      <LocaleSwitcher />
      <Probe />
    </I18nProvider>,
  )
}

function choose(value: string) {
  fireEvent.change(screen.getByRole('combobox'), { target: { value } })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  window.localStorage.clear()
  document.documentElement.removeAttribute('lang')
  document.documentElement.removeAttribute('dir')
})

describe('i18n', () => {
  it('defaults to English outside a provider', () => {
    render(<Probe />)

    expect(screen.getByText('en:Products')).toBeInTheDocument()
  })

  it('starts ltr and en by default', () => {
    renderApp()

    expect(document.documentElement).toHaveAttribute('dir', 'ltr')
    expect(document.documentElement).toHaveAttribute('lang', 'en')
  })

  it('flips dir and lang when switching to ar and back', () => {
    renderApp()

    choose('ar')
    expect(document.documentElement).toHaveAttribute('dir', 'rtl')
    expect(document.documentElement).toHaveAttribute('lang', 'ar')

    choose('en')
    expect(document.documentElement).toHaveAttribute('dir', 'ltr')
    expect(document.documentElement).toHaveAttribute('lang', 'en')
  })

  it('persists the locale and restores it on remount', () => {
    const first = renderApp()
    choose('ar')
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe('ar')
    first.unmount()

    renderApp()

    expect(document.documentElement).toHaveAttribute('dir', 'rtl')
    expect(screen.getByRole('combobox')).toHaveValue('ar')
  })

  it('falls back to en for an invalid stored value', () => {
    window.localStorage.setItem(STORAGE_KEY, 'fr')

    renderApp()

    expect(document.documentElement).toHaveAttribute('lang', 'en')
    expect(document.documentElement).toHaveAttribute('dir', 'ltr')
  })

  it('translates to Arabic under ar', () => {
    renderApp()

    choose('ar')

    expect(screen.getByText(`ar:${CATALOGS.ar.products}`)).toBeInTheDocument()
    expect(translate('ar', 'products')).not.toBe(translate('en', 'products'))
  })

  it('falls back to en when reading storage throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })

    renderApp()

    expect(screen.getByText('en:Products')).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('dir', 'ltr')
  })

  it('keeps working when writing storage throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota', 'QuotaExceededError')
    })

    renderApp()
    choose('ar')

    expect(document.documentElement).toHaveAttribute('dir', 'rtl')
    expect(screen.getByText(`ar:${CATALOGS.ar.products}`)).toBeInTheDocument()
  })

  it('renders Arabic products with locale-aware prices and bdi', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            items: [
              { id: 1, sku: 'A-1', name: 'Widget', price: 1250, currency: 'USD' },
            ],
            next_cursor: null,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    vi.stubEnv('VITE_API_BASE_URL', 'http://api.test')
    render(
      <I18nProvider>
        <LocaleSwitcher />
        <ProductsPage />
      </I18nProvider>,
    )

    choose('ar')
    fireEvent.change(screen.getByLabelText(CATALOGS.ar.tenantId), {
      target: { value: '7' },
    })
    fireEvent.click(screen.getByRole('button', { name: CATALOGS.ar.load }))

    const item = await screen.findByRole('listitem')
    const price = formatPrice(1250, 'USD', 'ar')
    expect(price).not.toBe(formatPrice(1250, 'USD', 'en'))
    expect(item.textContent).toContain(price)
    expect(item.querySelector('bdi')).toHaveAttribute('dir', 'ltr')
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
      CATALOGS.ar.products,
    )
  })

  it('maps locales to directions', () => {
    expect(dirFor('ar')).toBe('rtl')
    expect(dirFor('en')).toBe('ltr')
  })

  it('has the same keys in both catalogs', () => {
    expect(Object.keys(CATALOGS.ar).sort()).toEqual(
      Object.keys(CATALOGS.en).sort(),
    )
  })
})
