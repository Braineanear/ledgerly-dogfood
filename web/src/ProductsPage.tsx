import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { fetchProducts } from './products'
import type { Product, ProductPage } from './products'

function formatPrice(product: Product): string {
  if (product.price === null || product.currency === null) {
    return '-'
  }
  try {
    const formatter = new Intl.NumberFormat('en', {
      style: 'currency',
      currency: product.currency,
    })
    const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2
    return formatter.format(product.price / 10 ** digits)
  } catch {
    return `${product.price} ${product.currency}`
  }
}

function ProductsPage() {
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
      setError('Enter a tenant id.')
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
        setError(err instanceof Error ? err.message : 'Request failed')
      }
    } finally {
      if (controller.current === current) {
        setLoading(false)
      }
    }
  }

  return (
    <section>
      <h2>Products</h2>
      <form onSubmit={onSubmit}>
        <label>
          Tenant id
          <input
            value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
          />
        </label>
        <button type="submit">Load</button>
      </form>
      {loading && <p role="status">Loading products...</p>}
      {error && <p role="alert">{error}</p>}
      {page && page.items.length === 0 && <p>No products found.</p>}
      {page && page.items.length > 0 && (
        <ul>
          {page.items.map((product) => (
            <li key={product.id}>
              {product.sku} - {product.name} - {formatPrice(product)}
            </li>
          ))}
        </ul>
      )}
      {page?.next_cursor && (
        <p>Only the first page of products is shown.</p>
      )}
    </section>
  )
}

export default ProductsPage
