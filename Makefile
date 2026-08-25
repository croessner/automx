PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

VERSION ?= $(shell $(PYTHON) scripts/project-version.py)
PYTHON_IMAGE ?= python:3.14.7-slim-trixie
PYTHON_BASE_DIGEST ?= unresolved
REVISION ?= $(shell git rev-parse HEAD 2>/dev/null || printf unknown)
BUILD_REASON ?= local
IMAGE ?= automx:dev
MOJO_IMAGE ?= automx-mojo:dev
STANDALONE_DIR ?= dist/standalone
PACKAGE_ROOT ?= dist/package-root

.PHONY: bootstrap test coverage lint format typecheck audit check dist workflow-check \
	docker-build docker-build-mojo mojo-smoke e2e sbom sbom-mojo scan scan-mojo \
	standalone package-root release-guardrails clean

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

dist:
	$(BIN)/python -m build

workflow-check:
	actionlint

docker-build:
	docker build \
		--build-arg BUILD_REASON=$(BUILD_REASON) \
		--build-arg PYTHON_BASE_DIGEST=$(PYTHON_BASE_DIGEST) \
		--build-arg PYTHON_IMAGE=$(PYTHON_IMAGE) \
		--build-arg REVISION=$(REVISION) \
		--build-arg VERSION=$(VERSION) \
		--tag $(IMAGE) .

docker-build-mojo:
	docker build \
		--file Dockerfile-mojo \
		--build-arg BUILD_REASON=$(BUILD_REASON) \
		--build-arg PYTHON_BASE_DIGEST=$(PYTHON_BASE_DIGEST) \
		--build-arg PYTHON_IMAGE=$(PYTHON_IMAGE) \
		--build-arg REVISION=$(REVISION) \
		--build-arg VERSION=$(VERSION) \
		--tag $(MOJO_IMAGE) .

mojo-smoke: docker-build-mojo
	docker run --rm $(MOJO_IMAGE) --version

e2e:
	contrib/e2e/run.sh

sbom: docker-build
	mkdir -p dist/sbom
	syft docker:$(IMAGE) \
		-o spdx-json=dist/sbom/automx.spdx.json \
		-o cyclonedx-json=dist/sbom/automx.cdx.json
	$(BIN)/python -m json.tool dist/sbom/automx.spdx.json >/dev/null
	$(BIN)/python -m json.tool dist/sbom/automx.cdx.json >/dev/null

sbom-mojo: docker-build-mojo
	mkdir -p dist/sbom
	syft docker:$(MOJO_IMAGE) \
		-o spdx-json=dist/sbom/automx-mojo.spdx.json \
		-o cyclonedx-json=dist/sbom/automx-mojo.cdx.json
	$(BIN)/python -m json.tool dist/sbom/automx-mojo.spdx.json >/dev/null
	$(BIN)/python -m json.tool dist/sbom/automx-mojo.cdx.json >/dev/null

scan: sbom
	trivy sbom --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 dist/sbom/automx.cdx.json
	trivy image --scanners secret --exit-code 1 $(IMAGE)

scan-mojo: sbom-mojo
	trivy sbom --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 dist/sbom/automx-mojo.cdx.json
	trivy image --scanners secret --exit-code 1 $(MOJO_IMAGE)

standalone:
	PYTHON_BIN=$(BIN)/python scripts/build-standalone.sh $(STANDALONE_DIR)
	$(STANDALONE_DIR)/automx/automx config validate \
		--config contrib/e2e/automx.conf \
		--domain example.test

package-root: standalone
	scripts/build-package-root.sh $(STANDALONE_DIR)/automx $(PACKAGE_ROOT)

release-guardrails: check coverage audit dist workflow-check e2e scan scan-mojo package-root

clean:
	$(BIN)/python -m pip uninstall -y automx || true
