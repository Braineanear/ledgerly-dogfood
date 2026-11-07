import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { I18nContext } from './context'
import type { I18nValue } from './context'
import { STORAGE_KEY, dirFor, pickInitialLocale, translate } from './messages'
import type { Locale } from './messages'

function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(pickInitialLocale)

  useEffect(() => {
    document.documentElement.lang = locale
    document.documentElement.dir = dirFor(locale)
    try {
      window.localStorage.setItem(STORAGE_KEY, locale)
    } catch {
      // Storage may be unavailable; the locale just won't persist.
    }
  }, [locale])

  const value = useMemo<I18nValue>(
    () => ({ locale, setLocale, t: (key) => translate(locale, key) }),
    [locale],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export default I18nProvider
