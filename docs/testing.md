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

Mobileconfig tests cover password-free plain profiles, in-process CMS signing,
key/certificate matching and permissions, signature tampering, preservation of
valid pre-signed static profiles, CLI byte/status separation, and signed remote
probe handling.

`make e2e` builds `contrib/e2e/compose.yaml`, starts the service as UID 10001 on
a read-only filesystem, and invokes `automx probe all`. The stack uses synthetic
`.test` data and no external DNS, mail server, or identity provider. A local
non-root CoreDNS fixture proves the installed `dns check` command against
CNAME, SRV, PACC TXT, A, and AAAA data, including PACC's semantic TXT matching.
The same stack executes all local `render` schemas through the installed CLI
before checking DNS publication. The stack proves protocol contracts, not
interoperability with a particular third-party client.

`make sbom` uses Syft to create SPDX JSON and CycloneDX JSON in `dist/sbom/`.
`make scan` gates fixed high/critical findings from that final-filesystem SBOM
and performs a Trivy image secret scan. Generated artifacts are ignored and
must be regenerated for each release image.

## Release and GitHub gates

`make workflow-check` validates every GitHub Actions workflow with Actionlint.
`make mojo-smoke` builds the Mojo interop image and executes its installed CLI.
`make scan-mojo` creates and scans a separate SBOM for that final filesystem.
CI also builds and inspects the native AMD64 DEB/RPM and ARM64 DEB artifacts on
matching GitHub-hosted runners before a release branch can be promoted.

`make standalone` builds the self-contained runtime used by Linux packages and
executes CLI version and configuration smokes. `make package-root` stages its
systemd unit, operator example, documentation, and runtime in the filesystem
layout consumed by the DEB/RPM jobs. The release workflow then invokes the
repository-owned, shell-free `scripts/build-linux-package.py` helper with an
explicit package format, normalized version, native architecture, package root,
and output directory.

`make release-guardrails` combines the Python quality, coverage, audit,
distribution, workflow, E2E, both image-scan, and package-root gates. See
[Releases and GitHub supply chain](releasing.md) for the branch, tag, GHCR, and
artifact publication contracts.
