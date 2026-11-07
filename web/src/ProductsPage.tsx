import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { formatPrice } from './price'
import { fetchProducts } from './products'
import type { ProductPage } from './products'
import { useI18n } from './i18n/context'

function ProductsPage() {
  const { locale, t } = useI18n()
  const [tenantId, setTenantId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState<ProductPage | null>(null)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const id = tenantId.trim()
    if (!id) {
      setPage(null)
      setError(t('enterTenantId'))
      return
    }
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setLoading(true)
    setError(null)
    setPage(null)
    try {
      const result = await fetchProducts(id, current.signal)
      if (controller.current === current) {
        setPage(result)
      }
    } catch (err) {
      if (controller.current === current) {
        setError(err instanceof Error ? err.message : t('requestFailed'))
      }
    } finally {
      if (controller.current === current) {
        setLoading(false)
      }
    }
  }

  return (
    <section>
      <h2>{t('products')}</h2>
      <form onSubmit={onSubmit}>
        <label>
          {t('tenantId')}
          <input
            value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
          />
        </label>
        <button type="submit">{t('load')}</button>
      </form>
      {loading && <p role="status">{t('loading')}</p>}
      {error && <p role="alert">{error}</p>}
      {page && page.items.length === 0 && <p>{t('noProducts')}</p>}
      {page && page.items.length > 0 && (
        <ul>
          {page.items.map((product) => {
            const price =
              product.price === null || product.currency === null
                ? '-'
                : formatPrice(product.price, product.currency, locale)
            return (
              <li key={product.id}>
                <bdi dir="ltr">
                  {product.sku} - {product.name} - {price}
                </bdi>
              </li>
            )
          })}
        </ul>
      )}
      {page?.next_cursor && <p>{t('firstPageOnly')}</p>}
    </section>
  )
}

export default ProductsPage
