# automx product and security policy

## Supported baseline

automx 1.2 supports CPython 3.14 and the dependency ranges declared in
`pyproject.toml`. The supported server interface is ASGI. Historical Python 2,
Python 3.8, WSGI, mod_wsgi, and `automx-test` deployments are unsupported.

The implemented protocol versions and their normative sources are listed in
`docs/protocols/status.md`. Internet-Drafts can change incompatibly; an upgrade
requires a source review, contract-test updates, and a migration note.

## Security properties

The following properties are release requirements:

- untrusted XML cannot load DTDs, expand entities, access the network, or exceed
  the request limit;
- request secrets and identifiers are absent from access logs and error bodies;
- transport security fails closed unless an administrator explicitly enables a
  legacy plain mail transport;
- public OAuth metadata never contains a client secret and never represents
  automx as a registration endpoint;
- Autodiscover v2 cannot turn request data into a target URL;
- scripts run without a shell and with resource limits, SQL uses bound
  parameters, and LDAP validates server certificates;
- mobileconfig profiles do not embed passwords;
- production containers run non-root and support a read-only root filesystem;
- release images have SPDX and CycloneDX SBOMs and no known fixed high/critical
  vulnerability accepted without a documented decision.

## Data and logging

automx processes account identifiers only to resolve a configuration response.
It does not require mailbox passwords. Access logs are limited to HTTP method,
matched route template, and status; concrete path parameters are not logged.
Operators must keep backend credentials outside the repository and mount
configuration read-only with permissions appropriate to the runtime identity.

## Vulnerability reporting and updates

Report suspected vulnerabilities privately to the repository owner using the
security contact configured by the hosting platform. Do not include production
credentials, personal mailbox data, or destructive proof-of-concept traffic.

Maintainers should acknowledge reproducible reports, assess affected supported
versions, add a regression test, publish a fixed release, regenerate SBOMs, and
document any operator action. Public disclosure should follow coordinated
release of the fix. This file does not promise a response SLA.

## Engineering and release integrity

Security-sensitive changes require a focused reproducer or contract test before
the implementation. Shared validation, normalization, and rendering rules have
one authoritative implementation; copy-paste security logic is not accepted.
Technical comments, documentation, commit messages, and release notes are
English-only.

Published commits use an approved semantic prefix and a concise headline with a
bullet-list body. Maintainers stage and inspect only intended paths, exclude
ignored scratch/build material, and run the repository release gates against
the exact commit being pushed. Default-branch and release-tag pushes originate
from a clean checkout; vulnerability or secret-scan findings block publication
unless a documented maintainer decision explicitly accepts the risk. The remote
ref is read back after publication and must equal the intended local commit.

## Out of scope by design

automx does not provision DNS, register OAuth clients, validate external issuer
interoperability, act as an identity provider, or test actual mailbox login.
The CLI emits DNS plans and protocol probes but performs no provider mutation.
