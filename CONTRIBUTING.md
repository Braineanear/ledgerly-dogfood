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

## Pre-commit hook (optional)

You can run ruff automatically before each commit:

```sh
python -m pip install pre-commit
pre-commit install
pre-commit run --all-files
```

The last command is optional and checks every file once. The hook runs
`ruff check` only, with no autofix and no formatting, on `shared/`, `api/`,
and `worker/`. It is local and optional, and it does not replace
`make lint`, which remains the gate. The `CI / test` job still runs only
`make test`.

The hook pins its own ruff version in `.pre-commit-config.yaml`, which may
differ from the ruff installed in your virtual environment, so results can
differ between the two.

## Dependency updates

Renovate is configured in `renovate.json`. It opens one pull request a week,
on Monday before 6am UTC, that groups all minor and patch updates under the
name "minor and patch updates". All package managers Renovate detects are in
scope.

Major updates are never grouped or automerged. Renovate opens one only after
a maintainer approves it on the Renovate dependency dashboard.

The `CI / test` job runs only `make test`, so run `make lint` and `make build` locally on the
grouped pull request before merging it. `.github/` is not covered by
CODEOWNERS, so a review of `renovate.json` is not enforced.

## Branches and branch protection

Work on short-lived topic branches and open pull requests against the
default branch.

`.github/CODEOWNERS` assigns `api/`, `worker/`, `shared/`, and `web/` to
`@Braineanear`. `infra/` and `.github/` are not covered by it.

CI runs two jobs. `test`, shown as `CI / test`, runs only `make test`. Lint
is not a CI check, so run `make lint` locally before opening a pull request.

The `commitlint` job, shown as `CI / commitlint`, runs only on pull requests.
It enforces Conventional Commits (for example `feat: add export`) on every
commit in the pull request, using `commitlint.config.mjs`. It is not a
required check until a maintainer enables it.

Maintainers can apply this recommended protection in GitHub:

- Require pull requests before merging.
- Require the `CI / test` status check.
- Optionally require code-owner review.

This repository change does not alter any GitHub settings. None of this
protection is enforced until a maintainer enables it, and CODEOWNERS only
affects review when code-owner review is required.

GitHub does not let an author approve their own pull request. Requiring
code-owner review with a sole owner therefore needs a maintainer decision,
such as a bypass for the owner or a second reviewer.

## Run components locally

Use separate terminals for each runtime component:

```sh
make api-dev
make worker-dev
make web-dev
```

The `make dev` target only prints this guidance. It does not manage background
processes.
