// Development-only proxy. It forwards GET requests for a tenant's products
// to the API and attaches the bearer token on the server side, so the token
// never reaches the browser bundle. It does no browser authentication and no
// tenant authorisation.

export type ProxyEnv = Record<string, string | undefined>

type ProxyRequest = {
  method?: string
  url?: string
  headers: Record<string, string | string[] | undefined>
}

export type ProxyConfig = {
  target: string
  changeOrigin: boolean
  rewrite: (path: string) => string
  bypass: (req: ProxyRequest) => false | undefined
}

const DEFAULT_TARGET = 'http://localhost:8000'
const PREFIX = '/api'
const ALLOWED_PATH =
  /^\/api\/tenants\/(?!\.{1,2}\/)[^/?#]+\/products\/?(\?.*)?$/

export function buildProxy(env: ProxyEnv): Record<string, ProxyConfig> {
  const token = env.API_TOKEN

  return {
    [PREFIX]: {
      target: env.API_PROXY_TARGET || DEFAULT_TARGET,
      changeOrigin: true,
      rewrite: (path) =>
        path.startsWith(PREFIX) ? path.slice(PREFIX.length) : path,
      bypass: (req) => {
        if (req.method !== 'GET' || !ALLOWED_PATH.test(req.url ?? '')) {
          return false
        }
        // Never forward credentials supplied by the browser.
        delete req.headers.authorization
        if (token) {
          req.headers.authorization = `Bearer ${token}`
        }
        return undefined
      },
    },
  }
}
