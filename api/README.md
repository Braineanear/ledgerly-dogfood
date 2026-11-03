# Ledgerly API

`ledgerly-api` is the FastAPI application scaffold for Ledgerly. It does not
connect to databases, queues, or external services. It exposes two health
endpoints:

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
enabled.

## Test

Run the API smoke test through the root target:

```sh
make test
```
