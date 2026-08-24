# automx repository instructions

These instructions apply to the whole repository.

## Working contract

- Treat the current working tree as the starting state. Preserve unrelated
  maintainer changes and do not reset, overwrite, or reclassify them as foreign.
- For planned modernization work, follow the numbered prompt packs in the
  ignored `temp/prompts/` directory strictly in order. A prompt is complete only
  after its focused tests and `git diff --check` pass.
- Make protocol and security changes test-first. Reproduce a defect with the
  narrowest useful contract test, implement the correction, then run affected
  tests before broader gates.
- Keep the service pure ASGI. Do not reintroduce WSGI adapters, hand-written HTTP
  dispatch, import-time configuration I/O, or an alternate rendering path.
- Preserve the dependency direction documented in `docs/architecture.md`.
  HTTP and CLI code consume configuration/domain/renderers; renderers must not
  read HTTP state, environment variables, or backend credentials.
- Apply DRY and composition-first OOP consistently. Keep responsibilities
  small, cohesive, and testable; extract shared behavior instead of copying it.
- Write code comments, technical documentation, commit messages, and release
  notes in English. Document new or materially changed private helpers when
  their responsibility or boundary is not already self-evident.

## Git integration

- Stage only the intended repository paths. Keep ignored prompt packs,
  scratch evidence, virtual environments, caches, build outputs, and generated
  local SBOMs out of commits unless an artifact is explicitly versioned.
- Before committing, inspect the staged name/status list, staged diff summary,
  staged patch, and `git diff --cached --check`. Confirm that deletions are
  intentional and that no secret-like or unrelated material is staged.
- Use an English `Prefix: Concise headline` subject. Approved prefixes are
  `Add`, `Change`, `Fix`, `Remove`, `Refactor`, `Test`, `Docs`, `Build`, `Ci`,
  `Vendor`, `Security`, and `Chore`. Follow it with a short bullet-list body
  covering essential implementation, compatibility, validation, and operator
  impact.
- Split unrelated work when no single approved prefix and headline accurately
  describes the change. A bounded modernization whose code, tests,
  documentation, container, and migration are one acceptance unit may remain
  one commit.
- Integrate from the real repository, not a disposable clone or temporary
  worktree. Do not push unless the user authorizes it. Never force-push unless
  the user explicitly authorizes the exact ref and risk.
- Before a push, ensure the required gates cover the exact commit being
  published and the checkout is clean. After pushing, read back the remote ref
  and verify that its object ID equals local `HEAD`.

## Protocol work

- Read the current primary specification before changing a protocol contract.
  Record the exact Internet-Draft version; never describe a draft as an RFC.
- Mail Autoconfig, both Microsoft Autodiscover schemas, experimental
  Autodiscover v2, PACC, Mobileconfig, and OAuth/DCR boundaries need positive and
  negative contract tests.
- Treat Autodiscover v2 as experimental and configuration-only. Never derive a
  target URL from request input or follow a user-selected URL.
- automx is not an OAuth authorization server or DCR endpoint. Publish no
  client secret and do not invent a `registration_endpoint`.
- PACC JSON and its DNS digest are a byte-level pair. Any renderer change must
  update digest tests and exercise remote/local parity.

## Security and privacy

- Never put passwords, client secrets, authorization headers, cookies, or real
  account data in source, fixtures, logs, CLI arguments, images, SBOMs, or review
  artifacts. Use `.test` names and visibly synthetic values.
- Keep request and response bodies bounded. XML parsing must disable DTDs,
  entities, huge trees, and network access. Reject insecure transport by default.
- Dynamic commands run without a shell and with timeout/output bounds. SQL uses
  bound parameters. LDAP certificate verification remains fail-closed.
- CLI DNS functionality is read-only unless a future user explicitly requests
  and authorizes a separately designed apply workflow.

## Required gates

Run the narrowest affected tests while developing. Before handoff run:

```console
make check
make coverage
make audit
make e2e
make scan IMAGE=automx:dev
git diff --check
```

Also build both sdist and wheel, validate repository skills, search for stale
WSGI/legacy CLI references and secret-like material, and compare every requested
item with concrete code/test/documentation evidence.

When the task requests independent Claude review, run it only after internal
gates. Reproduce each plausible finding locally, fix it test-first, rerun affected
gates, and repeat the independent review until no substantiated in-scope finding
remains. Do not treat reviewer output as proof without local verification.

End modernization handoffs with a section titled exactly
`Review und Ist/Soll-Abgleich`.
