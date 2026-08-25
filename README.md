# automx

automx is a standards-oriented automatic account configuration service for
mail and groupware clients. Version 3.0 is a Python 3.14, FastAPI, and pure-ASGI
modernization of the original automx codebase. The current preview is
`3.0.0-beta.1`.

It serves:

- Mail Autoconfig XML 1.2;
- Microsoft Autodiscover XML for Outlook and MobileSync;
- a deliberately narrow, experimental Autodiscover v2 subset;
- PACC JSON according to `draft-ietf-mailmaint-pacc-03`;
- password-free Apple Mail `.mobileconfig` profiles;
- OAuth public-client metadata without publishing client secrets.

PACC, Mail Autoconfig 1.2, and OAuth Public Clients are Internet-Drafts. Their
implemented versions are pinned in [Protocol status](docs/protocols/status.md).

## Quick start

Python 3.14 is required.

```console
python3.14 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/automx config validate --config contrib/e2e/automx.conf
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

## Operator CLI

The CLI replaces the historical `automx-test` shell script and is split into
maintainable Python subcommand modules.

```console
automx config validate --config /etc/automx/automx.conf
automx openapi check --config /etc/automx/automx.conf
automx openapi export --config /etc/automx/automx.conf --output openapi.json
automx render autoconfig --config /etc/automx/automx.conf \
  --email probe@example.com
automx render autodiscover --config /etc/automx/automx.conf \
  --email probe@example.com --schema outlook
automx render pacc --config /etc/automx/automx.conf --domain example.com
automx pacc digest --config /etc/automx/automx.conf --domain example.com
automx dns records --config /etc/automx/automx.conf \
  --domain example.com --service-host config.example.net
automx dns check --config /etc/automx/automx.conf \
  --service-host config.example.net --nameserver 192.0.2.53
automx probe all --base-url https://autodiscover.example.com \
  --email probe@example.com --include-experimental
```

Render commands write the exact local protocol bytes without starting a server.
DNS commands generate or verify the complete read-only deployment contract;
none of these commands modifies external state. A protected
probe can read `username:password` from an explicitly named environment
variable with `--basic-auth-env`; credentials are never accepted as CLI
arguments.

## Documentation

- [Architecture](docs/architecture.md)
- [Configuration reference](docs/configuration.md)
- [ASGI and container deployment](docs/deployment.md)
- [CLI, DNS, and OpenAPI](docs/cli.md)
- [Protocol status and normative sources](docs/protocols/status.md)
- [OAuth, OIDC discovery, and DCR](docs/protocols/oauth-dcr.md)
- [PACC deployment](docs/protocols/pacc.md)
- [E2E, SBOM, and security scans](docs/testing.md)
- [Migration from automx 1.x](docs/migration.md)
- [Troubleshooting](docs/troubleshooting.md)

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
