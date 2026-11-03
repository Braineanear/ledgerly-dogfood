PYTHON ?= .venv/bin/python
PNPM ?= pnpm
TERRAFORM ?= terraform

.PHONY: test lint build verify infra-validate api-dev worker-dev web-dev dev

test:
	$(PYTHON) -m pytest shared/tests api/tests worker/tests
	$(PNPM) --dir web test

lint:
	$(PYTHON) -m ruff check shared api worker
	$(PNPM) --dir web lint

build:
	$(PYTHON) -m build shared
	$(PYTHON) -m build api
	$(PYTHON) -m build worker
	$(PNPM) --dir web build

infra-validate:
	$(TERRAFORM) -chdir=infra fmt -check
	$(TERRAFORM) -chdir=infra init -backend=false
	$(TERRAFORM) -chdir=infra validate

verify: test lint build infra-validate

api-dev:
	$(PYTHON) -m uvicorn ledgerly_api.main:app --reload

worker-dev:
	$(PYTHON) -m ledgerly_worker.main

web-dev:
	$(PNPM) --dir web dev

dev:
	@printf '%s\n' 'Run `make api-dev`, `make worker-dev`, and `make web-dev` in separate terminals.'
