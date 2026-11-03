# Ledgerly worker

`ledgerly-worker` is the placeholder background-worker package for Ledgerly.
It currently starts and exits without connecting to queues, databases,
schedulers, or external services.

## Install for local development

From the repository root, install the shared package and worker in editable
mode:

```sh
python -m pip install -e shared
python -m pip install -e worker
```

The worker depends on `ledgerly-shared`, so install the local shared package
first or alongside the worker.

## Run the placeholder

Run the worker with its package entry point:

```sh
ledgerly-worker
```

Or use the root development target:

```sh
make worker-dev
```

Both commands intentionally perform no jobs.
