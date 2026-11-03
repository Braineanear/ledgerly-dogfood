# Ledgerly

Ledgerly is a multi-tenant inventory and billing platform in its initial scaffold
stage. The repository is a monorepo for the following components:

- `api/`: Python FastAPI application.
- `worker/`: Python background-job process.
- `shared/`: Python package shared by the API and worker.
- `web/`: TypeScript React application built with Vite and managed with pnpm.
- `infra/`: Terraform configuration for Google Cloud.

PostgreSQL and Redis are planned dependencies for future application work. They
are not provisioned by this repository, and the initial API and worker scaffolds
do not require either service.

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
- `make infra-validate`: format-check, initialize without a backend, and
  validate Terraform configuration.
- `make verify`: run all repository quality gates.
