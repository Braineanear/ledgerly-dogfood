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

## Automation

The root Makefile exposes these commands:

- `make test`: run Python and web tests.
- `make lint`: run Python and web linters.
- `make build`: build Python packages and the web application.
- `make seed`: write 2 tenants and 20 products into the database selected by
  `DATABASE_URL`, which must be set. Run the Alembic migration first; see
  [api/README.md](api/README.md#seed-data).
- `make infra-validate`: format-check, initialize without a backend, and
  validate Terraform configuration.
- `make verify`: run all repository quality gates.
