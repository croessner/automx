---
name: automx-protocol-contracts
description: Implement or review automx Autoconfig, Autodiscover, PACC, Mobileconfig, or OAuth/DCR behavior against exact primary specifications.
---

# automx protocol contracts

Read root `AGENTS.md` and `docs/protocols/status.md`. Open the current primary
source for the protocol being changed and confirm whether the pinned version is
still current. Identify Internet-Drafts as work in progress.

Add a failing contract test before changing a renderer. Check exact namespaces,
element names, media types, error behavior, authentication ordering, and byte
determinism as applicable. Include malformed and adversarial input tests.

Keep Autodiscover v2 configuration-only and experimental. Keep OAuth discovery
and DCR at the external authorization server: automx may publish a valid HTTPS
issuer or public client identifier, but no secret and no invented registration
endpoint. Treat PACC response bytes and the UAAC1 DNS TXT digest as one contract.

Run the focused renderer/request tests, the OpenAPI check, `make check`, and
`git diff --check`. Run E2E whenever a public response or route changes.
