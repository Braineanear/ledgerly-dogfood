# Ledgerly shared package

`ledgerly-shared` contains the small set of types shared by the API and worker.
It intentionally has no persistence, business rules, or external-service
integration.

## Install for local development

From the repository root, install the package in editable mode:

```sh
python -m pip install -e shared
```

Install this package before, or alongside, the API and worker packages so they
can import `ledgerly_shared`.

## Models

`ledgerly_shared.models` exports `PlaceholderModel`, a typed placeholder for
future shared model design.
