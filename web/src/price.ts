export function formatPrice(minorUnits: number, currency: string): string {
  try {
    const formatter = new Intl.NumberFormat('en', {
      style: 'currency',
      currency: currency.toUpperCase(),
    })
    const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2
    return formatter.format(minorUnits / 10 ** digits)
  } catch {
    return `${minorUnits} ${currency}`
  }
}
