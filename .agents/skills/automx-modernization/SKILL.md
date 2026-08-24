---
name: automx-modernization
description: Modernize or refactor automx Python architecture, packaging, configuration backends, or ASGI runtime while preserving compatibility and repository gates.
---

# automx modernization

Read root `AGENTS.md`, `docs/architecture.md`, and the relevant numbered prompt
under `temp/prompts/` before editing. Treat the current tree as the starting
state and preserve unrelated maintainer work.

Work test-first and keep the dependency flow HTTP/CLI -> configuration/domain ->
renderer. Do not add WSGI compatibility or a second protocol implementation.
Normalize legacy INI values only at the configuration boundary and keep domain
objects immutable and strictly validated.

Run focused tests after each change. Before handoff run `make check`, coverage,
package build, and `git diff --check`; add E2E/SBOM gates when the runtime or
deployment surface changes. Finish with a concrete requirement-to-evidence
review rather than a general summary.
