import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import App from './App'
import I18nProvider from './i18n/I18nProvider'
import { CATALOGS } from './i18n/messages'

describe('App', () => {
  afterEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('lang')
    document.documentElement.removeAttribute('dir')
  })

  it('renders the placeholder application', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'Ledgerly' }),
    ).toBeInTheDocument()
  })

  it('renders Arabic and rtl after picking ar', () => {
    render(
      <I18nProvider>
        <App />
      </I18nProvider>,
    )

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: 'ar' },
    })

    expect(
      screen.getByRole('heading', { name: CATALOGS.ar.title }),
    ).toBeInTheDocument()
    expect(document.documentElement).toHaveAttribute('dir', 'rtl')
  })
})
