# Migration from automx 1.x

automx 1.2 is a deliberate runtime and deployment break: Python 3.14 and ASGI
replace the historical mixed Python 2/3 and WSGI stack.

1. Rebuild the virtual environment; do not reuse an old `venv/`.
2. Install from `pyproject.toml` with the backend extras actually required.
3. Run `automx config validate` for every configured domain.
4. Replace mod_wsgi/Gunicorn-WSGI entrypoints with `automx serve` or another
   standards-compliant ASGI process manager.
5. Put a maintained TLS reverse proxy in front of the loopback-bound service.
6. Replace `automx-test` with `automx probe all` and use the DNS/OpenAPI commands
   for deployment material.
7. Generate PACC DNS records only after the final configuration is deployed;
   its TXT digest is byte-sensitive.

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
