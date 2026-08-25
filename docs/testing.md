# Tests, E2E, SBOM, and scans

Run the local gates from a Python 3.14 virtual environment:

```console
make check
make coverage
make audit
```

`make check` runs Ruff, strict mypy, and pytest. Contract tests cover model and
configuration validation, safe parsing, protocol renderers, exact namespace and
error behavior, OpenAPI, CLI exit codes, deterministic PACC and DNS output,
normalized DNS drift/error handling, and container configuration. Resolver
unit tests use an injected in-memory implementation and never depend on public
DNS.

`make e2e` builds `contrib/e2e/compose.yaml`, starts the service as UID 10001 on
a read-only filesystem, and invokes `automx probe all`. The stack uses synthetic
`.test` data and no external DNS, mail server, or identity provider. A local
non-root CoreDNS fixture proves the installed `dns check` command against
CNAME, SRV, PACC TXT, A, and AAAA data, including PACC's semantic TXT matching.
The same stack executes all local `render` schemas through the installed CLI
before checking DNS publication.
The stack proves protocol contracts, not
interoperability with a particular third-party client.

`make sbom` uses Syft to create SPDX JSON and CycloneDX JSON in `dist/sbom/`.
`make scan` gates fixed high/critical findings from that final-filesystem SBOM
and performs a Trivy image secret scan. Generated artifacts are ignored and
must be regenerated for each release image.
