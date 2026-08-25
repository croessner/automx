# Troubleshooting

Start with the offline contract before restarting or changing a deployment:

```console
automx config validate --config /etc/automx/automx.conf --domain example.test
automx openapi check --config /etc/automx/automx.conf
```

Use the narrowest check that matches the symptom:

| Symptom | First evidence | Next check |
| --- | --- | --- |
| Container does not become ready | `docker compose ps` and the readiness healthcheck | Confirm the mounted configuration path and run `config validate` |
| One protocol document is rejected | Local `render` output and exit status | Run the matching focused `probe` against public HTTPS |
| PACC digest differs | `probe pacc --config ...` byte-parity result | Compare authoritative and recursive views with `dns check` |
| DNS publication appears incomplete | One explicit resolver result | Query each authoritative server separately before public recursors |
| Experimental v2 returns 404 | Configured `autodiscover_v2` value | Confirm the requested protocol has an allowlisted configured URL |

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

`automx dns check` reports `MISS` when a required owner/type has no answer,
`DRIFT` when published RDATA differs or CNAME indirection replaces a direct
record required by the generated plan, and `ERROR` when the selected resolver
view could not be completed. An error is not evidence that a record is absent;
this includes failure of either canonical-host address-family lookup. Run
authoritative servers separately from public recursive resolvers to distinguish
source drift from propagation or cache state. The command never repairs DNS.
Additional SRV values and PACC rollover TXT records are not drift when the
generated SRV member or any valid UAAC1 SHA-256 digest still matches.

Do not disable TLS verification to diagnose production. The probe CLI permits
plain HTTP only with an explicit flag intended for isolated test networks; it
does not provide an insecure HTTPS mode and requires TLS 1.3 or newer.
