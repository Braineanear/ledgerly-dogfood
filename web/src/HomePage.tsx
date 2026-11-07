import ProductsPage from './ProductsPage'
import { useI18n } from './i18n/context'
import LocaleSwitcher from './i18n/LocaleSwitcher'

function HomePage() {
  const { t } = useI18n()
  return (
    <main>
      <h1>{t('title')}</h1>
      <LocaleSwitcher />
      <ProductsPage />
    </main>
  )
}

export default HomePage
