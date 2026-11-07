# Ledgerly API

`ledgerly-api` is the FastAPI application for Ledgerly. It needs a database
(see [Database](#database)) and Redis. It exposes two health endpoints:

- `GET /health` returns `{"status": "ok"}`.
- `GET /health/version` returns `{"sha": "<git sha>"}`.
- `GET /version` returns `{"version": "<package version>"}`.

The sha is resolved once at startup (when the app is created) from the
`GIT_SHA` environment variable, then from `git rev-parse HEAD`, and otherwise
is `"unknown"`. Installed or containerised builds without a `.git` directory
should set `GIT_SHA`, or they will report `"unknown"`.

## Install for local development

From the repository root, install the shared package and API in editable mode:

```sh
python -m pip install -e shared
python -m pip install -e api
```

The API declares a dependency on `ledgerly-shared`; installing the local shared
package first allows pip to resolve that dependency during local development.

## Run locally

Start the placeholder application from the repository root:

```sh
make api-dev
```

This runs Uvicorn with the `ledgerly_api.main:app` import path and reload
enabled. `DATABASE_URL` and `REDIS_URL` are required and have no defaults. If
either is missing, startup exits with a one-line error naming the missing
variable, for example `Missing required environment variable(s): REDIS_URL`.
`API_TOKEN` is unchanged (see [Authentication](#authentication)):

```sh
export DATABASE_URL=sqlite:///./ledgerly.db
export REDIS_URL=redis://localhost:6379/0
API_TOKEN=change-me make api-dev
```

## Authentication

`API_TOKEN` is required and has no default. If it is unset or empty, the API
still starts, but every `/tenants` request is rejected with 401.

`GET /health`, `GET /health/version` and `GET /version` are public. All `/tenants` endpoints
need an `Authorization: Bearer <token>` header:

```sh
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/tenants/1
```

A missing or wrong token returns 401 `application/problem+json` with a
`WWW-Authenticate: Bearer` header.

## Stock movements

`POST /tenants/{tenant_id}/movements` records a stock movement. It needs the
bearer token. The JSON body is `{"product_id": 1, "warehouse": "main",
"quantity": 5}`. A negative `quantity` is an outbound movement, and zero is
rejected. It returns 201 with `{id, product_id, warehouse, quantity}`. An
unknown tenant or product returns 404 `application/problem+json`.

```sh
curl -X POST -H "Authorization: Bearer $API_TOKEN" \
  -H "Idempotency-Key: order-42" -H "Content-Type: application/json" \
  -d '{"product_id": 1, "warehouse": "main", "quantity": 5}' \
  http://localhost:8000/tenants/1/movements
```

### Idempotency-Key

- The `Idempotency-Key` header is optional (1 to 255 characters). Without it,
  every request creates a movement.
- Keys are scoped per tenant. The same key under two tenants is independent.
- Repeating a key with the same body returns the first response (same status
  and body) and writes no second movement.
- Repeating a key with a different body returns 409 `application/problem+json`
  and writes nothing.
- Only 201 responses are stored. Errors such as 404 are not stored, so the key
  can be reused after a failure.
- Keys never expire in this version.

Apply the Alembic migration (`make migrate`) so the `idempotency_key` table
exists.

## Product search

`GET /tenants/{tenant_id}/products?q=<text>` filters the tenant's products
by name. It needs the bearer token.

- The match is a case-insensitive substring match on the product name.
- `%` and `_` in `q` match literally. They are not wildcards.
- `q` has a maximum length of 255. A longer value returns 422
  `application/problem+json`.
- An empty or whitespace-only `q` means no filter.
- Results stay in id order, and the `next_cursor` cursor works as before.
- The route is tenant-scoped. There is no bare `/products` route.

```sh
curl -H "Authorization: Bearer $API_TOKEN" \
  "http://localhost:8000/tenants/1/products?q=widget&limit=10"
```

### Migration 0009

Migration 0009 is for Postgres only. It does two things:

- It runs `CREATE EXTENSION IF NOT EXISTS pg_trgm`. The database user needs
  the privilege to `CREATE EXTENSION`.
- It creates the GIN index `ix_product_name_trgm` on `product.name`, using
  `gin_trgm_ops`.

On sqlite it does nothing. Downgrade drops only the index and leaves the
extension installed.

An optional live test runs the migration against a real Postgres. Set
`LEDGERLY_TEST_PG_URL` to the URL of an empty database, or one already at
0009. Without the variable the test is skipped.

## Product CSV export

`GET /tenants/{tenant_id}/products.csv` streams all of the tenant's products
as CSV. It needs the bearer token and has no filter.

- The columns are `id`, `sku`, `name`, `price`, `currency`, with a header row.
- `price` is in minor units (an integer), as in the JSON API.
- Rows are ordered by `id`.
- A null price or currency is an empty cell.
- `sku` and `name` values that start with `=`, `+`, `-`, `@`, a tab or a
  carriage return get a leading apostrophe, so spreadsheets do not run them
  as formulas.
- An unknown tenant returns 404 `application/problem+json`. A missing or
  wrong token returns 401.

```sh
curl -H "Authorization: Bearer $API_TOKEN" \
  -o products.csv http://localhost:8000/tenants/1/products.csv
```

## Admin stats

`ADMIN_KEY` is required to enable `GET /admin/stats`. Send it as the
`X-Admin-Key` header:

```sh
curl -H "X-Admin-Key: $ADMIN_KEY" http://localhost:8000/admin/stats
```

If `ADMIN_KEY` is unset or empty, the route fails closed: every request is
rejected with 401, even with an empty header. A missing or wrong header also
returns 401 `application/problem+json`, without a `WWW-Authenticate` header.

Compose passes `ADMIN_KEY` to the api service from the environment or `.env`.
`.env.example` holds a placeholder; set your own value and never commit it.

## Database

The API reads the `DATABASE_URL` environment variable when a request needs a
database. It is required and has no default; for SQLite, a relative file URL
such as `sqlite:///./ledgerly.db` is relative to the directory the API is
started from. A session is opened per request and closed
afterwards. The API does not create tables, so run the Alembic migration first.
The preferred way is `make migrate` from the repository root:

```sh
DATABASE_URL=sqlite:///./ledgerly.db make migrate
```

Alternatively, run Alembic directly from the same directory you start the API
from:

```sh
DATABASE_URL=sqlite:///./ledgerly.db python -m alembic -c shared/alembic.ini upgrade head
```

With the raw command, adjust the `-c` path to point at `shared/alembic.ini` from your working
directory. Always set `DATABASE_URL` explicitly when running the migration so
it creates the same file the API opens. Use the same `DATABASE_URL` for both.

## Seed data

After the Alembic migration above, `make seed` writes 2 tenants and 20
products (10 per tenant):

```sh
DATABASE_URL=sqlite:///./ledgerly.db make seed
```

`DATABASE_URL` selects the target database and must be set. Use the same value as for the
migration. The seed only runs when the `tenant` table is empty. It exits nonzero and writes
nothing in these cases:

- exit code 1: the tenant table already has rows.
- exit code 2: the schema is missing (run the migration first).

## Dependency licences

The API declares `sqlalchemy>=2.0` directly because it imports it. SQLAlchemy
is released under the MIT licence, which is compatible with this project. Its
installed metadata may not carry a licence field, so automated licence checks
that rely on local metadata can report it as unknown.

## Test

Run the API smoke test through the root target:

```sh
make test
```

# corpus probe
