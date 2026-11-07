import { describe, expect, it } from 'vitest'
import { formatPrice } from './price'

describe('formatPrice', () => {
  it('formats USD minor units', () => {
    expect(formatPrice(250, 'USD')).toBe('$2.50')
  })

  it('accepts a lowercase currency code', () => {
    expect(formatPrice(250, 'usd')).toBe('$2.50')
  })

  it('formats zero', () => {
    expect(formatPrice(0, 'USD')).toBe('$0.00')
  })

  it('treats JPY as zero-decimal', () => {
    expect(formatPrice(500, 'JPY')).toBe('¥500')
  })

  it('falls back for an invalid currency', () => {
    expect(formatPrice(250, 'XXXX')).toBe('250 XXXX')
  })

  it('formats negative minor units', () => {
    expect(formatPrice(-250, 'USD')).toBe('-$2.50')
  })

  it('formats three-decimal currencies like KWD', () => {
    expect(formatPrice(2500, 'KWD').replace(/\s/g, ' ')).toBe('KWD 2.500')
  })

  it('formats large minor unit values with thousand separators', () => {
    expect(formatPrice(123456789, 'USD')).toBe('$1,234,567.89')
  })

  it('uses the locale argument for digits', () => {
    const result = formatPrice(250, 'USD', 'ar-EG')

    expect(result).toMatch(/[٠-٩]/)
    expect(result).not.toBe(formatPrice(250, 'USD'))
  })

  it('falls back when given an empty currency string', () => {
    expect(formatPrice(250, '')).toBe('250 ')
  })
})
