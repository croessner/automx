# Troubleshooting

Start with the offline contract:

```console
automx config validate --config /etc/automx/automx.conf --domain example.com
automx openapi check --config /etc/automx/automx.conf
```

Exit status 2 means an operator input, configuration, filesystem, or protocol-
representation error. The CLI writes that error to stderr and never includes
request credentials.

If readiness fails, confirm the mounted path matches `AUTOMX_CONFIG` or the
explicit `--config` value. If a generated profile fails, validate the exact
domain because domain-specific sections override `[global]`.

An Autodiscover XML HTTP 200 can still contain a protocol error body; inspect
`ErrorCode`. Code 600 denotes malformed/unsupported request XML. A v2 404 may
mean the feature is disabled or the requested protocol has no configured URL.

For PACC mismatch, fetch the decoded body without transformation and compare it
with `automx probe pacc --config ...`. Reverse proxies must not pretty-print,
compress incorrectly, or otherwise alter decoded JSON bytes without updating
the DNS digest.

Do not disable TLS verification to diagnose production. The probe CLI permits
plain HTTP only with an explicit flag intended for isolated test networks; it
does not provide an insecure HTTPS mode.
