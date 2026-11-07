export type Locale = 'en' | 'ar'

export const LOCALES: readonly Locale[] = ['en', 'ar']

export const DEFAULT_LOCALE: Locale = 'en'

export const STORAGE_KEY = 'ledgerly.locale'

const en = {
  title: 'Ledgerly',
  products: 'Products',
  tenantId: 'Tenant id',
  load: 'Load',
  enterTenantId: 'Enter a tenant id.',
  loading: 'Loading products...',
  noProducts: 'No products found.',
  firstPageOnly: 'Only the first page of products is shown.',
  requestFailed: 'Request failed',
  language: 'Language',
}

export type MessageKey = keyof typeof en

type Catalog = Record<MessageKey, string>

// Arabic strings are agent-written; they need native-speaker review.
const ar: Catalog = {
  title: 'ليدجرلي',
  products: 'المنتجات',
  tenantId: 'معرّف المستأجر',
  load: 'تحميل',
  enterTenantId: 'أدخل معرّف المستأجر.',
  loading: 'جارٍ تحميل المنتجات...',
  noProducts: 'لا توجد منتجات.',
  firstPageOnly: 'يتم عرض الصفحة الأولى من المنتجات فقط.',
  requestFailed: 'فشل الطلب',
  language: 'اللغة',
}

export const CATALOGS: Record<Locale, Catalog> = { en, ar }

export function dirFor(locale: Locale): 'rtl' | 'ltr' {
  return locale === 'ar' ? 'rtl' : 'ltr'
}

export function translate(locale: Locale, key: MessageKey): string {
  return CATALOGS[locale][key]
}

export function isLocale(value: unknown): value is Locale {
  return LOCALES.some((locale) => locale === value)
}

export function pickInitialLocale(): Locale {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return isLocale(stored) ? stored : DEFAULT_LOCALE
  } catch {
    return DEFAULT_LOCALE
  }
}
