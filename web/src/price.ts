export function formatPrice(
  minorUnits: number,
  currency: string,
  locale = 'en',
): string {
  try {
    const formatter = new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currency.toUpperCase(),
    })
    const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2
    return formatter.format(minorUnits / 10 ** digits)
  } catch {
    return `${minorUnits} ${currency}`
  }
}
