# Container security and software bill of materials

The release container is built from
`python:3.14.7-slim-trixie`. The base image resolved to digest
`sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4`
during the 2026-08-24 verification run.

The runtime image:

- upgrades Debian packages before the application is copied;
- contains no compiler or build toolchain;
- runs as the fixed unprivileged user and group `10001`;
- is compatible with a read-only root filesystem and dropped Linux capabilities;
- exposes only the ASGI service on port 8000.

`make sbom` creates SPDX JSON and CycloneDX JSON inventories in `dist/sbom/`
with Syft. `make scan` scans that generated CycloneDX inventory for fixed high
and critical vulnerabilities and separately scans the image filesystem for
secrets with Trivy.

## 2026-08-24 assessment

The first scan identified fixed high-severity vulnerabilities in the Debian
`util-linux` package family. Rebuilding with current Debian security updates
upgraded those packages from `2.41-5` to `2.41-5+deb13u1`. The follow-up scan
reported no high or critical vulnerabilities in the generated image SBOM and
no embedded secrets.

Trivy's direct image inventory also imported stale Python package records from
third-party base-image attestations for packages that were absent from both the
runtime filesystem and the application virtual environment. The vulnerability
gate therefore uses the SBOM generated directly from the final filesystem by
Syft. The separate Trivy secret scan continues to inspect the image itself.

Run `make e2e` to additionally prove that the Compose service runs as a
non-root user on a read-only root filesystem and that its public protocol
endpoints remain usable.
