# Load tests

A read-only [Locust](https://locust.io) load test for Ledgerly's product
endpoints. Part of Ledgerly.

There is no bare `/products` route. The test exercises:

- `GET /tenants/{tenant_id}/products` (with `limit`)
- the same list, following `next_cursor` for up to two more pages
- `GET /tenants/{tenant_id}/products/{product_id}`, using ids seen in the
  list responses

The test never writes data.

## Setup

```sh
python3 -m venv .venv-load
. .venv-load/bin/activate
pip install -r load/requirements.txt
```

## Configuration

| Variable | Meaning |
| --- | --- |
| `LEDGERLY_API_TOKEN` (or `API_TOKEN`) | Bearer token the API expects |
| `LEDGERLY_TENANT_ID` | Id of an existing tenant |

The locustfile exits with a message if either is missing. Do not commit
token values.

The API must be running with `API_TOKEN`, `DATABASE_URL` and `REDIS_URL`
set. The tenant and its products must already exist, for example via
`make seed`. The API listens on port 8000 by default.

## Running

Headless:

```sh
locust -f load/locustfile.py --host http://localhost:8000 \
    --headless -u 10 -r 2 -t 1m
```

Web UI (then open http://localhost:8089):

```sh
locust -f load/locustfile.py --host http://localhost:8000
```

## Notes

`load/` is not covered by `make test` or `make lint`. It is a manual tool:
it is not run in CI and has no unit tests or declared check. Run it by hand
with the commands above.
