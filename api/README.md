# Ledgerly API

`ledgerly-api` is the FastAPI application scaffold for Ledgerly. It currently
provides only application bootstrap behavior and does not connect to databases,
queues, or external services.

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
