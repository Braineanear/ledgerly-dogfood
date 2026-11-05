# Ledgerly API

`ledgerly-api` is the FastAPI application for Ledgerly. It needs a database
(see [Database](#database)) and Redis. It exposes two health endpoints:

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

`GET /health` and `GET /health/version` are public. All `/tenants` endpoints
need an `Authorization: Bearer <token>` header:

```sh
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/tenants/1
```

A missing or wrong token returns 401 `application/problem+json` with a
`WWW-Authenticate: Bearer` header.

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
