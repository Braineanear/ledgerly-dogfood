import { useI18n } from './context'
import { LOCALES, isLocale } from './messages'
import type { Locale } from './messages'

const NAMES: Record<Locale, string> = {
  en: 'English',
  ar: 'العربية',
}

function LocaleSwitcher() {
  const { locale, setLocale, t } = useI18n()
  return (
    <label>
      {t('language')}
      <select
        value={locale}
        onChange={(event) => {
          const value = event.target.value
          if (isLocale(value)) {
            setLocale(value)
          }
        }}
      >
        {LOCALES.map((item) => (
          <option key={item} value={item}>
            {NAMES[item]}
          </option>
        ))}
      </select>
    </label>
  )
}

export default LocaleSwitcher
