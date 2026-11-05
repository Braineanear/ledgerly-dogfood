export interface Product {
  id: number
  sku: string
  name: string
  price: number | null
  currency: string | null
}

export interface ProductPage {
  items: Product[]
  next_cursor: string | null
}

export async function fetchProducts(
  tenantId: string,
  signal?: AbortSignal,
): Promise<ProductPage> {
  const base = import.meta.env.VITE_API_BASE_URL ?? '/api'
  const url = `${base}/tenants/${encodeURIComponent(tenantId)}/products`
  const response = await fetch(url, { signal })
  if (!response.ok) {
    let message = response.statusText
    try {
      const problem = await response.json()
      message = problem.detail || problem.title || message
    } catch {
      // body is not JSON; keep the status text
    }
    throw new Error(
      message ? `${response.status}: ${message}` : `${response.status}`,
    )
  }
  return (await response.json()) as ProductPage
}
