PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

IMAGE ?= automx:dev

.PHONY: bootstrap test coverage lint format typecheck audit check docker-build docker-build-mojo e2e sbom scan clean

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e '.[dev]'

test:
	$(BIN)/pytest

coverage:
	$(BIN)/pytest --cov=automx --cov-report=term-missing

lint:
	$(BIN)/ruff check .

format:
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

typecheck:
	$(BIN)/mypy

audit:
	$(BIN)/python -m pip_audit --cache-dir .cache/pip-audit

check: lint typecheck test

docker-build:
	docker build --build-arg VERSION=3.0.0-beta.1 --tag $(IMAGE) .

docker-build-mojo:
	docker build --file Dockerfile-mojo --build-arg VERSION=3.0.0-beta.1 --tag $(IMAGE) .

e2e:
	contrib/e2e/run.sh

sbom: docker-build
	mkdir -p dist/sbom
	syft docker:$(IMAGE) -o spdx-json=dist/sbom/automx.spdx.json -o cyclonedx-json=dist/sbom/automx.cdx.json
	$(BIN)/python -m json.tool dist/sbom/automx.spdx.json >/dev/null
	$(BIN)/python -m json.tool dist/sbom/automx.cdx.json >/dev/null

scan: sbom
	trivy sbom --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 dist/sbom/automx.cdx.json
	trivy image --scanners secret --exit-code 1 $(IMAGE)

clean:
	$(BIN)/python -m pip uninstall -y automx || true
