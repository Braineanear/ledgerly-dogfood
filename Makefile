PYTHON ?= .venv/bin/python
PNPM ?= pnpm
TERRAFORM ?= terraform
SYFT ?= syft
DOCKER ?= docker
API_IMAGE ?= ledgerly-api:sbom

.PHONY: test lint build verify sbom infra-validate api-dev worker-dev web-dev dev seed migrate recompute-stock clean-caches

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
	$(TERRAFORM) -chdir=infra fmt -check -recursive
	$(TERRAFORM) -chdir=infra init -backend=false
	$(TERRAFORM) -chdir=infra validate

verify: test lint build infra-validate

sbom:
	@if ! command -v $(SYFT) >/dev/null 2>&1; then \
		echo 'syft not installed; skipping sbom (see https://github.com/anchore/syft)'; \
	elif ! command -v $(DOCKER) >/dev/null 2>&1; then \
		echo 'docker not installed; skipping sbom'; \
	else \
		set -e; \
		$(DOCKER) build -f api/Dockerfile -t $(API_IMAGE) .; \
		$(SYFT) scan $(API_IMAGE) -o spdx-json=sbom-api.spdx.json; \
	fi

clean-caches:
	rm -rf .pytest_cache .ruff_cache

api-dev:
	$(PYTHON) -m uvicorn ledgerly_api.main:app --reload

seed:
	$(PYTHON) -m ledgerly_api.seed

migrate:
	$(PYTHON) -m alembic -c shared/alembic.ini upgrade head

worker-dev:
	$(PYTHON) -m ledgerly_worker.main

recompute-stock:
	$(PYTHON) -m ledgerly_worker.recompute

web-dev:
	$(PNPM) --dir web dev

dev:
	@printf '%s\n' 'Run `make api-dev`, `make worker-dev`, and `make web-dev` in separate terminals.'
