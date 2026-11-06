# Ledgerly worker

`ledgerly-worker` is the placeholder background-worker package for Ledgerly.
It starts a no-op run loop that stays alive until it receives SIGINT (Ctrl-C)
or SIGTERM, then exits 0. The placeholder loop does not connect to queues,
databases, schedulers, or external services, and it processes no real jobs.
The separate, opt-in nightly scheduler (see below) does use a database.

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

## Nightly recompute scheduler (opt-in)

The scheduler runs the stock recompute once a night. It is separate from the
placeholder loop and is not started by `ledgerly-worker` or `make worker-dev`:

```sh
DATABASE_URL=... python -m ledgerly_worker.scheduler
```

Configuration:

- `DATABASE_URL` is required, as for `make recompute-stock`. If it is missing,
  the scheduler exits 2 at startup.
- `RECOMPUTE_AT` is the daily run time as `HH:MM` in UTC. The default is
  `02:00`. An invalid value exits 2 at startup.

Behaviour:

- It does not run on startup. It waits for the next run time.
- Missed runs are skipped. If the worker was down, or a run lasted past the
  next slot, it waits for the next future slot and never runs a slot twice.
- A run that raises or returns a non-zero exit code is logged, and the
  scheduler carries on to the next night. It does not retry the same night.
- SIGINT or SIGTERM stops it and it exits 0. A stop that arrives during a run
  takes effect after the run returns.

The recompute takes an exclusive lock on the tenant row, so writers to that
tenant block while it runs. Run only one scheduler instance; overlapping
instances would queue on that lock.

A simpler alternative is to run `make recompute-stock` from external cron or a
Kubernetes CronJob, with no scheduler process.
