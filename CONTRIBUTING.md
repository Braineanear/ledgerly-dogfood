# Contributing to Ledgerly

Ledgerly is a monorepo with Python packages in `shared/`, `api/`, and
`worker/`, plus a pnpm-managed web application in `web/` and Terraform in
`infra/`.

## Prerequisites

Install Python, pnpm, and Terraform. Python packages use editable installs for
local development; the web application uses pnpm and its committed lockfile.

## Set up Python packages

Create and activate a virtual environment from the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install the shared package before installing the API and worker packages:

```sh
python -m pip install -e shared
python -m pip install -e api
python -m pip install -e worker
python -m pip install pytest ruff build
```

The API and worker both depend on the local shared package. Reinstall the
relevant editable package after changing its package metadata.

## Set up the web application

Install the web dependencies from the repository root:

```sh
pnpm --dir web install --frozen-lockfile
```

Use `pnpm --dir web dev`, `pnpm --dir web lint`, `pnpm --dir web test`, and
`pnpm --dir web build` to work with the web application directly.

## Check your changes

Run the repository quality gates after installing dependencies:

```sh
make test
make lint
make build
make infra-validate
make verify
```

`make infra-validate` runs Terraform initialization with its backend disabled
and validates configuration only. It does not create infrastructure.

## Run components locally

Use separate terminals for each runtime component:

```sh
make api-dev
make worker-dev
make web-dev
```

The `make dev` target only prints this guidance. It does not manage background
processes.
