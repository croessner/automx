# automx

> **automx, reloaded — standards-first configuration for modern mail clients.**

automx is a standards-oriented automatic account configuration service for
mail and groupware clients. Version 3.0 is a Python 3.14, FastAPI, and pure-ASGI
modernization of the original automx codebase. The current preview is
`3.0.0-beta.3`.

automx is developed in collaboration with sys4 AG.

It serves:

- Mail Autoconfig XML 1.2;
- Microsoft Autodiscover XML for Outlook and MobileSync;
- a deliberately narrow, experimental Autodiscover v2 subset;
- PACC JSON according to `draft-ietf-mailmaint-pacc-03`;
- password-free Apple Mail `.mobileconfig` profiles with optional verified
  in-process CMS signing;
- OAuth public-client metadata without publishing client secrets.

PACC, Mail Autoconfig 1.2, and OAuth Public Clients are Internet-Drafts. Their
implemented versions are pinned in [Protocol status](docs/protocols/status.md).

## Quick start

Python 3.14 is required.

```console
python3.14 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/automx config validate --config contrib/e2e/automx.conf \
  --domain example.test
.venv/bin/automx serve --config contrib/e2e/automx.conf --port 8000
```

The interactive OpenAPI UI is then available at `http://127.0.0.1:8000/docs`
and the machine-readable document at `/openapi.json`.

For an isolated container proof:

```console
make e2e
```

The E2E stack builds the image, proves its non-root and read-only operation,
then probes every public protocol family through the installed `automx` CLI.

## Production operator path

Use a reviewed configuration and an image pinned by digest. The complete
[deployment guide](docs/deployment.md) covers the reverse proxy, verification,
and rollback contract.

```console
automx config validate --config /etc/automx/automx.conf --domain example.test
docker compose config --quiet
docker compose up -d --wait
automx probe all --base-url https://ua-auto-config.example.test \
  --email probe@example.test --config /etc/automx/automx.conf \
  --domain example.test
```

## Operator tools

The modular CLI validates configuration, renders exact protocol bytes, exports
OpenAPI, generates and checks read-only DNS plans, and probes deployments. See
the [CLI operator guide](docs/cli.md) for commands, output, exit status, and
safe all-domain examples. No CLI DNS command changes external state.

## Documentation

Operator guides:

- [Configuration reference](docs/configuration.md)
- [ASGI and container deployment](docs/deployment.md)
- [CLI, DNS, rendering, and remote probes](docs/cli.md)
- [Troubleshooting](docs/troubleshooting.md)
- [E2E, SBOM, and security scans](docs/testing.md)
- [Releases, GHCR images, and Linux packages](docs/releasing.md)
- [Migration from automx 1.x](docs/migration.md)

Architecture and protocol contracts:

- [Architecture](docs/architecture.md)
- [Protocol status and normative sources](docs/protocols/status.md)
- [OAuth, OIDC discovery, and DCR](docs/protocols/oauth-dcr.md)
- [PACC deployment](docs/protocols/pacc.md)

## Development gates

```console
make check
make coverage
make audit
make e2e
make scan IMAGE=automx:dev
```

Repository working rules are in [AGENTS.md](AGENTS.md). Product and security
boundaries are in [POLICY.md](POLICY.md). Licensed under GPL-3.0-or-later.
