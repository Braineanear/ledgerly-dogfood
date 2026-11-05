# Ledgerly worker

`ledgerly-worker` is the placeholder background-worker package for Ledgerly.
It starts a no-op run loop that stays alive until it receives SIGINT (Ctrl-C)
or SIGTERM, then exits 0. It does not connect to queues, databases,
schedulers, or external services, and it processes no real jobs.

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

Both commands start the no-op run loop and keep running until SIGINT or
SIGTERM, then exit 0. The loop does no real work.
