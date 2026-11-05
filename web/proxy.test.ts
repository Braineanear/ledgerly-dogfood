import { describe, expect, it } from 'vitest'
import { buildProxy } from './proxy'

type Req = Parameters<ReturnType<typeof buildProxy>['/api']['bypass']>[0]

function request(url: string, method = 'GET', headers: Req['headers'] = {}) {
  return { url, method, headers } as Req
}

describe('buildProxy', () => {
  it('targets localhost:8000 by default', () => {
    const config = buildProxy({})['/api']

    expect(config.target).toBe('http://localhost:8000')
    expect(config.changeOrigin).toBe(true)
  })

  it('uses API_PROXY_TARGET when set', () => {
    const config = buildProxy({ API_PROXY_TARGET: 'http://api:8000' })['/api']

    expect(config.target).toBe('http://api:8000')
  })

  it('strips the /api prefix', () => {
    const config = buildProxy({})['/api']

    expect(config.rewrite('/api/tenants/1/products?limit=5')).toBe(
      '/tenants/1/products?limit=5',
    )
  })

  it('attaches the bearer token when API_TOKEN is set', () => {
    const config = buildProxy({ API_TOKEN: 'secret-value' })['/api']
    const req = request('/api/tenants/1/products', 'GET', {
      authorization: 'Bearer from-browser',
    })

    expect(config.bypass(req)).toBeUndefined()
    expect(req.headers.authorization).toBe('Bearer secret-value')
  })

  it('forwards no Authorization header when API_TOKEN is unset', () => {
    const config = buildProxy({})['/api']
    const req = request('/api/tenants/1/products', 'GET', {
      authorization: 'Bearer from-browser',
    })

    expect(config.bypass(req)).toBeUndefined()
    expect(req.headers.authorization).toBeUndefined()
  })

  it('allows a trailing slash and a query string', () => {
    const config = buildProxy({})['/api']

    expect(config.bypass(request('/api/tenants/1/products/'))).toBeUndefined()
    expect(
      config.bypass(request('/api/tenants/1/products?limit=5')),
    ).toBeUndefined()
  })

  it.each(['POST', 'PUT', 'DELETE', 'PATCH'])('rejects %s', (method) => {
    const config = buildProxy({ API_TOKEN: 'secret-value' })['/api']
    const req = request('/api/tenants/1/products', method)

    expect(config.bypass(req)).toBe(false)
    expect(req.headers.authorization).toBeUndefined()
  })

  it.each([
    '/api/health',
    '/api/tenants/x/other',
    '/api/tenants/1/products/2',
    '/api/tenants//products',
    '/api/tenants/../products',
  ])('rejects the path %s', (url) => {
    const config = buildProxy({ API_TOKEN: 'secret-value' })['/api']
    const req = request(url)

    expect(config.bypass(req)).toBe(false)
    expect(req.headers.authorization).toBeUndefined()
  })
})
