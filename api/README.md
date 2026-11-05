# Ledgerly API

`ledgerly-api` is the FastAPI application for Ledgerly. It uses a SQLite
database (see [Database](#database)) and does not connect to queues or
external services. It exposes two health endpoints:

- `GET /health` returns `{"status": "ok"}`.
- `GET /health/version` returns `{"sha": "<git sha>"}`.

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
enabled. `API_TOKEN` must be set (see [Authentication](#authentication)):

```sh
API_TOKEN=change-me make api-dev
```

## Authentication

`API_TOKEN` is required and has no default. If it is unset or empty, every
`/tenants` request is rejected with 401.

`GET /health` and `GET /health/version` are public. All `/tenants` endpoints
need an `Authorization: Bearer <token>` header:

```sh
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/tenants/1
```

A missing or wrong token returns 401 `application/problem+json` with a
`WWW-Authenticate: Bearer` header.

## Database

The API reads the `DATABASE_URL` environment variable when a request needs a
database. It defaults to `sqlite:///./ledgerly.db`, a file relative to the
directory the API is started from. A session is opened per request and closed
afterwards. The API does not create tables, so run the Alembic migration first,
from the same directory you start the API from:

```sh
DATABASE_URL=sqlite:///./ledgerly.db python -m alembic -c shared/alembic.ini upgrade head
```

Adjust the `-c` path to point at `shared/alembic.ini` from your working
directory. The fallback URL in `alembic.ini` is `sqlite:///ledgerly.db`; setting
`DATABASE_URL` explicitly makes the migration create the same file the API
opens. Use the same `DATABASE_URL` for both.

## Seed data

After the Alembic migration above, `make seed` writes 2 tenants and 20
products (10 per tenant):

```sh
DATABASE_URL=sqlite:///./ledgerly.db make seed
```

`DATABASE_URL` selects the target database and defaults to
`sqlite:///./ledgerly.db`. Use the same value as for the migration. The seed
only runs when the `tenant` table is empty. It exits nonzero and writes
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
