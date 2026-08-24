# syntax=docker/dockerfile:1.12

ARG PYTHON_IMAGE=python:3.14.7-slim-trixie

FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /build

RUN python -m venv /opt/automx
COPY pyproject.toml README.md LICENSE ./
COPY src/automx ./src/automx
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/automx/bin/python -m pip install .

FROM ${PYTHON_IMAGE} AS runtime

ARG VERSION=1.2.0
LABEL org.opencontainers.image.title="automx" \
      org.opencontainers.image.description="Standards-oriented automatic account configuration service" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="GPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/croessner/automx"

ENV PATH="/opt/automx/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTOMX_CONFIG=/etc/automx/automx.conf
WORKDIR /app

RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 automx \
    && useradd --uid 10001 --gid automx --no-create-home --home-dir /nonexistent automx
COPY --from=builder /opt/automx /opt/automx

USER automx:automx
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2).read()"]

ENTRYPOINT ["automx"]
CMD ["serve", "--config", "/etc/automx/automx.conf", "--host", "0.0.0.0", "--port", "8000"]
