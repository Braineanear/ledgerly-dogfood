# Ledgerly

Ledgerly is a multi-tenant inventory and billing platform in its initial scaffold
stage. The repository is a monorepo for the following components:

- `api/`: Python FastAPI application.
- `worker/`: Python background-job process.
- `shared/`: Python package shared by the API and worker.
- `web/`: TypeScript React application built with Vite and managed with pnpm.
- `infra/`: Terraform configuration for Google Cloud.

The API requires `DATABASE_URL` and `REDIS_URL`, with no defaults, and exits at
startup with a one-line error if either is missing. It needs the Alembic
migration run first; see [api/README.md](api/README.md). Neither service is
provisioned by this repository, and the worker scaffold does not require
either one.

The web app reaches the API through a development-only proxy; see
[web/README.md](web/README.md#reaching-the-api).

## Local setup

See [CONTRIBUTING.md](CONTRIBUTING.md) for the Python editable-install, pnpm,
and Terraform setup workflow. After dependencies are installed, run the
repository checks with:

```sh
make verify
```

## Development

Run each runtime component in a separate terminal:

```sh
make api-dev
make worker-dev
make web-dev
```

`make dev` prints the same guidance and intentionally does not start a process
supervisor.

## Docker Compose

`compose.yaml` runs `postgres`, `redis`, `migrate`, `api`, `worker` and `web`.

1. Copy `.env.example` to `.env` and fill in the values.
2. `POSTGRES_PASSWORD` and `POSTGRES_PASSWORD_URLENCODED` must be the same
   password, the second percent-encoded (`@` is `%40`, `:` is `%3A`, `/` is
   `%2F`, `#` is `%23`). Compose cannot check this.
3. Run `docker compose up --build`. Migrations run automatically through the
   `migrate` service before `api` starts.

The api listens on port 8000 and the web dev server on port 5173. To re-run
migrations manually, use `docker compose run --rm migrate`. Outside compose, run the same migrations
from the repository root with `DATABASE_URL=... make migrate`.

Variables use the `${VAR:-}` form, so `docker compose config` renders without
a `.env`, but real values must be set before `up`. The postgres and redis
images are pinned by digest, and `renovate.json` can keep the digests updated.

## Recomputing stock levels

The worker can rebuild every `StockLevel` quantity from the
`stock_movement` table. Run it with one of:

```sh
DATABASE_URL=... make recompute-stock
DATABASE_URL=... python -m ledgerly_worker.recompute [--tenant-id ID]
docker compose run worker python -m ledgerly_worker.recompute
```

`DATABASE_URL` is required; without it the job exits with code 2. The compose
`worker` service now provides it and waits for postgres and `migrate`.
`--tenant-id ID` limits the run to one tenant, which is recommended for
targeted runs because the job locks every product row in scope.

Invariant: after a run, each `StockLevel.quantity` equals the sum of movement
deltas for its tenant, product and warehouse. The result depends only on the
movements, so the job is idempotent: a second run changes nothing.

- `StockLevel` rows with no movements are reset to 0, not deleted. Back up or
  backfill seeded or legacy quantities as movements first.
- A negative total aborts the whole run with exit code 1 and no changes.
- Write movements only through `append_stock_movement`, which locks the
  product row. The recompute locks the same rows, so the two serialize on
  Postgres. Writers that skip the lock can be missed or lost.
- SQLite ignores `FOR UPDATE`, so the SQLite tests do not prove this locking.
  The Postgres test runs only when `TEST_POSTGRES_URL` is set.

## Working with Dikasta

Dikasta commands used with this repository:

- `dikasta login`: sign in.
- `dikasta doctor`: check the setup.
- `dikasta chat`: start a chat.

## Automation

The root Makefile exposes these commands:

- `make test`: run Python and web tests.
- `make lint`: run Python and web linters.
- `make build`: build Python packages and the web application.
- `make migrate`: apply the Alembic migrations to the database selected by
  `DATABASE_URL`, which must be set.
- `make seed`: write 2 tenants and 20 products into the database selected by
  `DATABASE_URL`, which must be set. Run the Alembic migration first; see
  [api/README.md](api/README.md#seed-data).
- `make recompute-stock`: recompute stock levels; see
  [Recomputing stock levels](#recomputing-stock-levels).
- `make infra-validate`: format-check, initialize without a backend, and
  validate Terraform configuration.
- `make verify`: run all repository quality gates.
