# Architecture

Ledgerly has four components: api, worker, shared and web. This page
lists the modules each one owns.

Convention: a module entry is a bullet line that starts with
"- Module: " followed by one backticked repo-relative path, then " - "
and the responsibility. Backticks are reserved for module entries. Each
section's first entry is the component's package or source directory.
A test in api/tests checks that every entry path exists.

Files at the repo root, such as config.py, are outside the four
components.

## api

- Module: `api/src/ledgerly_api` - FastAPI service package.
- Module: `api/src/ledgerly_api/main.py` - app factory, health and version routes.
- Module: `api/src/ledgerly_api/auth.py` - settings, startup validation and bearer token auth.
- Module: `api/src/ledgerly_api/db.py` - database URL, engine and session dependency.
- Module: `api/src/ledgerly_api/logging_config.py` - JSON log formatter and logging setup.
- Module: `api/src/ledgerly_api/problems.py` - problem+json error responses and handlers.
- Module: `api/src/ledgerly_api/products.py` - product create, list (cursor paging) and get routes.
- Module: `api/src/ledgerly_api/tenants.py` - tenant create and get routes.
- Module: `api/src/ledgerly_api/ready.py` - readiness checks for the database and Redis.
- Module: `api/src/ledgerly_api/request_id.py` - middleware that assigns a request id.
- Module: `api/src/ledgerly_api/seed.py` - seeds an empty, migrated database with tenants and products.

## worker

- Module: `worker/src/ledgerly_worker` - worker service package.
- Module: `worker/src/ledgerly_worker/main.py` - placeholder entry point that starts and exits.
- Module: `worker/src/ledgerly_worker/probe.py` - trivial probe module with no behavior yet.

## shared

- Module: `shared/src/ledgerly_shared` - package shared by api and worker.
- Module: `shared/src/ledgerly_shared/models.py` - placeholder dataclass model.
- Module: `shared/src/ledgerly_shared/orm.py` - SQLAlchemy models for tenants, products, stock and orders.
- Module: `shared/alembic` - Alembic environment and database migrations.

## web

- Module: `web/src` - React and TypeScript source directory.
- Module: `web/src/main.tsx` - browser entry point that mounts the app.
- Module: `web/src/App.tsx` - root component, currently a scaffold page.
