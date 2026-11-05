# Ledgerly web

This directory contains the Ledgerly web application. It is a
pnpm-managed Vite, React, and TypeScript project. It has a Products page that
lists the products of one tenant.

## Set up

From the repository root, install the locked dependencies:

```sh
pnpm --dir web install --frozen-lockfile
```

## Reaching the API

The browser calls the same-origin `/api` path. The Vite dev proxy forwards
`GET /api/tenants/{id}/products` to the API, strips the `/api` prefix and
attaches `Authorization: Bearer <API_TOKEN>`. Other methods and paths are not
forwarded. The page chooses the tenant through its tenant id input.

- Local development: `API_PROXY_TARGET` defaults to `http://localhost:8000`.
- Docker Compose: `API_PROXY_TARGET` is `http://api:8000`, and the web port
  is bound to loopback (`127.0.0.1:5173`).

Variables (see `web/.env.example`; copy it to `web/.env.local`):

- `API_PROXY_TARGET`: API base URL the proxy forwards to.
- `API_TOKEN`: bearer token the proxy sends. It is read only on the server
  side by the proxy, and Compose passes it through from the host environment.
- `VITE_API_BASE_URL`: base URL the browser calls, `/api` by default.

`VITE_` variables are public and compiled into the bundle. Never put the API
token or any other secret in one.

The proxy is development-only. It does no browser authentication and no
tenant authorisation, so anyone who can reach the dev server can read any
tenant's products. Do not expose it beyond localhost. Production needs a
reverse proxy or BFF that authenticates users, authorises the tenant and adds
the token.

## Commands

Run these commands from the repository root:

```sh
pnpm --dir web dev
pnpm --dir web lint
pnpm --dir web test
pnpm --dir web build
```

`make web-dev` starts the development server. The root `make test`, `make
lint`, and `make build` targets include the corresponding web commands.
