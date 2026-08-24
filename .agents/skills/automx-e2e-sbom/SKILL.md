---
name: automx-e2e-sbom
description: Build and verify the automx hardened container, protocol E2E stack, SBOM artifacts, or vulnerability and secret scan gates.
---

# automx E2E and supply chain

Read root `AGENTS.md`, `docs/testing.md`, and
`docs/security/container-scan.md`. Use only synthetic `.test` configuration and
never print environment or secret-bearing configuration.

Run `make e2e` to prove the image executes as non-root with a read-only root
filesystem and that the installed CLI passes all protocol probes. A passing
health check alone is not an E2E result.

Run `make sbom IMAGE=<exact-tag>` to generate both SPDX and CycloneDX JSON from
the final filesystem. Run `make scan IMAGE=<same-tag>` for fixed high/critical
vulnerabilities and the image secret scan. Investigate findings against the
actual final filesystem before changing policy or suppressing anything; record
the package, fixed version, and follow-up result. Do not use floating production
tags or add an ignore without an evidence-backed, narrowly scoped decision.
