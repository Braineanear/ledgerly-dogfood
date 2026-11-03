import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the placeholder application', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'Ledgerly' }),
    ).toBeInTheDocument()
  })
})
