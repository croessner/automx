# Migration from automx 1.x

automx 3.0 is a deliberate runtime and deployment break: Python 3.14 and ASGI
replace the historical mixed Python 2/3 and WSGI stack.

1. Rebuild the virtual environment; do not reuse an old `venv/`.
2. Install from `pyproject.toml` with the backend extras actually required.
3. Run `automx config validate` for every configured domain.
4. Replace mod_wsgi/Gunicorn-WSGI entrypoints with `automx serve` or another
   standards-compliant ASGI process manager.
5. Put a maintained TLS reverse proxy in front of the loopback-bound service.
6. Replace `automx-test` with `automx probe all`; use `automx dns records` to
   generate the plan and `automx dns check` to gate authoritative and recursive
   publication in deployment automation.
7. Generate PACC DNS records only after the final configuration is deployed;
   its TXT digest is byte-sensitive.

## PACC-02 to PACC-03 rollover

PACC-03 changes the submission service key from `smtp` to `submit`. This is a
wire-format change: even unchanged mail endpoints produce different JSON bytes
and therefore a different `_ua-auto-config` SHA-256 digest.

Perform a cache-safe rollover for every served domain:

1. Render the PACC-03 response and its new TXT record from the exact release
   configuration before changing the running service.
2. Publish both the existing PACC-02 TXT record and the new PACC-03 TXT record.
3. Wait at least the previous authoritative TTL and verify that both records are
   visible through authoritative and recursive resolvers.
4. Deploy the PACC-03 HTTP representation and verify its bytes against the new
   digest with `automx probe pacc` and `automx dns check`.
5. Keep both digests published for the longest applicable HTTP cache lifetime
   and DNS TTL, then remove the obsolete PACC-02 record.

Never publish only the new digest while serving the old representation, or the
new representation while publishing only the old digest. `automx dns check`
accepts a matching record in a multi-value TXT RRset specifically to support
this rollover.

Compatibility normalizations remain for `plaintext`, `encrypted`, `ssl`,
`starttls`, and the classic static/global/LDAP/SQL/script section model. Plain
transport now requires `allow_insecure=yes`. OAuth client secrets are rejected,
mobileconfig never embeds passwords, dynamic SQL interpolation is rejected, and
unsafe LDAP certificate modes are not accepted.

The historical `filter` backend and built-in memcache failure counter are not
carried forward: arbitrary account-rewriting subprocesses obscured validation,
and distributed HTTP rate limits belong at the trusted ingress. Use the bounded
`script` variable backend for explicit lookups and enforce request limits at the
reverse proxy or API gateway. The `file` backend remains for validated,
configuration-directory-local compatibility documents.

Autodiscover v2 is new, experimental, and off by default. Enable it only after
all returned HTTPS URLs are explicitly configured and tested.
