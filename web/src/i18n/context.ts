import { createContext, useContext } from 'react'
import { translate } from './messages'
import type { Locale, MessageKey } from './messages'

export type I18nValue = {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey) => string
}

export const I18nContext = createContext<I18nValue>({
  locale: 'en',
  setLocale: () => {},
  t: (key) => translate('en', key),
})

export function useI18n(): I18nValue {
  return useContext(I18nContext)
}
