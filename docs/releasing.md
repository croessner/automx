# Releases and GitHub supply chain

automx uses `features` for development and `main` for release-ready history.
Pull requests normally target `features`; a release is prepared by updating the
version and documentation there, passing the complete guardrails, and merging a
reviewed release commit into `main`. Releases use new SemVer tags in the form
`vMAJOR.MINOR.PATCH[-PRERELEASE]`. Historical tags keep their original names but
are not accepted by the new release workflow.

## Continuous integration

`.github/workflows/ci.yml` runs for both long-lived branches and their pull
requests. It checks Ruff, strict Mypy, tests, coverage, dependency audit, Python
distributions, and workflow syntax. Separate jobs run the complete Python
container E2E suite, a Mojo image smoke test, and native AMD64/ARM64 Linux
package builds through the same local action used by the release workflow.

All external actions are pinned to full commit IDs. Dependabot proposes Python,
GitHub Actions, and Docker dependency updates against `features`.

Run the equivalent local release gate before creating a tag:

```console
make release-guardrails
```

The target includes both container scans and the standalone package-root smoke.
It requires Docker, Actionlint, Syft, Trivy, and the `package` Python extra.

## Creating a release

1. Update the version in `pyproject.toml` and `src/automx/__init__.py`.
2. Update version-specific protocol and operator documentation.
3. Merge the reviewed release state into `main` and run `make release-guardrails`.
4. Create and push an annotated SemVer tag that exactly matches the project
   version, for example `v3.0.0-beta.2`.

The tag starts `.github/workflows/release.yml`. The workflow repeats the Python
gates, validates tag/version parity, builds sdist and wheel artifacts, calls the
container publication workflow, builds Linux packages, creates SHA-256 sums,
attests the artifacts, and publishes the GitHub release.

The release body combines a commit summary grouped by the repository's approved
commit prefixes with GitHub's pull-request and contributor release notes.
`.github/release.yml` categorizes breaking changes, features, fixes, security,
documentation, dependencies, and remaining changes.

## Public container images

Each release publishes linked OCI packages with SBOM and provenance:

| Implementation | Image | Platforms |
| --- | --- | --- |
| Python | `ghcr.io/croessner/automx` | `linux/amd64`, `linux/arm64` |
| Mojo interop | `ghcr.io/croessner/automx-mojo` | `linux/amd64` |

Pushes to `features` that change a runtime or Dockerfile publish the same two
platform sets under the mutable `dev` tag. These images are for integration
testing only and record the exact features commit in their OCI metadata.

Prereleases receive only their exact tag. Stable releases additionally receive
`latest`, `vMAJOR`, and `vMAJOR.MINOR`. Production deployments should still pin
the exact manifest digest.

The Dockerfiles link both packages to the public source repository. After each
publish the workflow logs out of GHCR and reads the manifest anonymously. A
private package therefore fails the release. If GitHub creates either package
as private despite the repository link, an owner must change its visibility to
Public in the package settings and rerun the job. GitHub does not allow a public
package to be made private again.

## Base-image refresh

The container workflow checks the latest stable release every day. It hashes
the exact upstream manifest for `python:3.14.7-slim-trixie` and compares that
value with the `io.automx.base.python.digest` label on both published images.
Only stale or missing images are rebuilt from the immutable release tag. The
exact release aliases are refreshed and an additional
`vVERSION-rebuild-YYYYMMDD-RUN` tag preserves the rebuild event. OCI labels
record the source revision, base digest, and build reason.

This refresh handles changed upstream manifests for the configured base tag.
Dependabot remains responsible for proposals that change the base-image version
itself.

## DEB and RPM packages

The release workflow builds a self-contained PyInstaller `onedir` runtime. It
does not depend on a compatible system Python. A repository-owned, shell-free
builder calls native `dpkg-deb` and `rpmbuild` commands with bounded arguments;
it copies the complete staged filesystem so payload filenames are never
reinterpreted as shell words. Release assets include DEB built on matching
`amd64` and `arm64` runners, plus RPM for `x86_64`.

The packages install:

- the runtime under `/opt/automx`;
- the CLI link `/usr/bin/automx`;
- `automx.service` under the systemd unit directory;
- an operator example under `/usr/share/doc/automx/automx.conf.example`.

Installation does not enable or start the service. Configure and validate it
first:

```console
sudo install -d -m 0750 /etc/automx
sudo install -m 0600 \
  /usr/share/doc/automx/automx.conf.example \
  /etc/automx/automx.conf
sudo automx config validate --config /etc/automx/automx.conf --domain example.test
sudo systemctl enable --now automx
sudo systemctl status automx
```

The unit uses `DynamicUser` and systemd credentials, so the source configuration
can remain root-only. Replace all reserved example values before activation.
