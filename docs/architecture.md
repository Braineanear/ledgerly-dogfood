# Architecture

Ledgerly has four components. Each section lists the modules it owns.

## api

The HTTP service that serves products and tenants, authenticates callers
and reports health.

- `api/src/ledgerly_api/main.py`: builds the app and health routes.
- `api/src/ledgerly_api/auth.py`: settings and bearer token checks.
- `api/src/ledgerly_api/admin.py`: admin-key guarded stats endpoint.
- `api/src/ledgerly_api/db.py`: database engine and sessions.
- `api/src/ledgerly_api/products.py`: product create, list and get.
- `api/src/ledgerly_api/tenants.py`: tenant handling.
- `api/src/ledgerly_api/problems.py`: problem-style error responses.
- `api/src/ledgerly_api/ready.py`: readiness probes.
- `api/src/ledgerly_api/request_id.py`: request id propagation.
- `api/src/ledgerly_api/logging_config.py`: JSON logging setup.

## worker

The background process that runs probes and recomputes stock.

- `worker/src/ledgerly_worker/main.py`: worker entry point.
- `worker/src/ledgerly_worker/probe.py`: probe logic.
- `worker/src/ledgerly_worker/recompute.py`: recompute jobs.

## shared

The library used by both api and worker.

- `shared/src/ledgerly_shared/models.py`: shared data models.
- `shared/src/ledgerly_shared/orm.py`: ORM table definitions.
- `shared/src/ledgerly_shared/stock.py`: stock calculations.

## web

The browser front end for browsing products.

- `web/src/main.tsx`: front-end entry point.
- `web/src/App.tsx`: top-level component.
- `web/src/ProductsPage.tsx`: products page.
- `web/src/products.ts`: products API client.
