# CLI, DNS, and OpenAPI

`automx` is the operator Swiss army knife. Each command has independent help:

```console
automx --help
automx probe all --help
```

## Configuration and serving

`automx config validate` parses the whole INI file and resolves a representative
profile. `automx serve` starts Uvicorn with untrusted proxy headers disabled.

## OpenAPI

FastAPI publishes OpenAPI 3.1 at `/openapi.json`. The offline contract uses the
same app factory:

```console
automx openapi check --config /etc/automx/automx.conf
automx openapi export --config /etc/automx/automx.conf --output openapi.json
```

JSON serialization is sorted and deterministic. Autodiscover v2 operations have
`x-automx-status: experimental`; health endpoints are deliberately excluded.

## Local protocol documents

`render` shows the exact bytes automx would serve after resolving the selected
configuration and backend. It is useful when reviewing a migration or client
configuration without starting HTTP or reducing the result to probe status:

```console
automx render autoconfig --config /etc/automx/automx.conf \
  --email probe@example.com
automx render autodiscover --config /etc/automx/automx.conf \
  --email probe@example.com --schema outlook
automx render autodiscover --config /etc/automx/automx.conf \
  --email probe@example.com --schema mobilesync
automx render pacc --config /etc/automx/automx.conf --domain example.com
```

Document bytes go directly to stdout without a banner, reformatting, or an
extra newline. Expected configuration and rendering errors go to stderr and
return exit status `2`. Redirect stdout to a file when needed. The commands use
the same profile resolution, dynamic backend, validated static-document, and
renderer service as ASGI. They accept no credentials or network/write options.
PACC output therefore has exact parity with `pacc digest`, `dns records`, the
HTTP response, and `probe pacc`.

## DNS records

```console
automx dns records --config /etc/automx/automx.conf \
  --domain example.com --service-host automx.example.net --format zone
```

The command emits Autoconfig and Autodiscover aliases, the Autodiscover SRV
record, the PACC service alias, and the exact UAAC1 TXT digest. `--format json`
is suitable for infrastructure tooling. Add `--all-domains` to generate the
complete configured non-wildcard domain set; omitting both domain selectors
retains the compatible single-domain behavior. This command is always
read-only and has no provider credentials or apply mode. A CNAME whose owner
name equals `--service-host` is omitted because the canonical service host must
publish A/AAAA records rather than an alias to itself.

## DNS verification

`dns check` compares published records with the same shared PACC document bytes
used by `render pacc` and `dns records`:

```console
automx dns check --config /etc/automx/automx.conf \
  --service-host autoconfig.example.net
automx dns check --config /etc/automx/automx.conf \
  --service-host autoconfig.example.net --nameserver 192.0.2.53
automx dns check --config /etc/automx/automx.conf \
  --service-host autoconfig.example.net --nameserver 1.1.1.1 --format json
```

The default is all configured non-wildcard domains. Use `--domain` for a
focused check. The command verifies every required CNAME, SRV, and TXT value,
reports CNAME indirection at a generated direct SRV/TXT owner as plan drift,
confirms that the canonical service host has A or AAAA data and is not itself a
CNAME, and recomputes each UAAC1 digest from the exact local PACC bytes. This
checks direct-owner publication parity, not only whether a recursive resolver
can eventually chase an alias to matching RDATA. CNAME records remain exact.
An SRV RRset may contain additional values, while its generated value must be
present. PACC TXT records are parsed according to PACC-03: tag order and
separator whitespace are insignificant, unknown future tags are ignored, and
any matching valid digest in a multi-record RRset passes. The digest itself is
still compared byte for byte. A failed A or AAAA lookup makes the canonical-host
check incomplete even if the other address family answers.

Without `--nameserver`, the system recursive resolver is used. Repeat
`--nameserver` to create one failover resolver pool (up to eight servers). The
per-attempt timeout stays bounded and the total lifetime scales with the pool so
each configured resolver can be tried. To prove independent DNS views, invoke
the command separately for every authoritative server and public
recursive resolver. `--port` supports isolated test or non-default resolver
ports. All queries have bounded per-query time and bounded parallelism.

Exit status `0` means complete and matching, `1` means a missing or mismatched
record, and `2` means configuration, input, or DNS lookup failure. Human output
labels each owner as `PASS`, `MISS`, `DRIFT`, or `ERROR`; deterministic JSON
contains the same result and summary. DNS verification is strictly read-only:
there is no update, provider credential, AXFR, or apply mode.

## Remote probes

Use `probe health`, `probe autoconfig`, `probe autodiscover`, `probe pacc`, or
`probe all`. HTTPS is required unless `--allow-insecure-http` is explicitly used
for an isolated local stack. Secure probes require TLS 1.3 or newer, matching
PACC-03's transport baseline. Redirects are not followed, responses are
bounded, and XML is parsed without DTD or entities.

`--include-experimental` adds Autodiscover v2. `--config PATH` makes the PACC
probe compare remote bytes with the local renderer. For HTTP Basic protection,
put `username:password` in an environment variable and pass only its name with
`--basic-auth-env`; never place a password on the command line.

Use a visibly synthetic local part and the domain-specific PACC hostname for a
production probe:

```console
automx probe all --base-url https://ua-auto-config.example.com \
  --email probe@example.com --config /etc/automx/automx.conf \
  --domain example.com
```

`probe` deliberately handles one domain per invocation so its origin, email
domain, and local parity selection remain explicit. A portable all-domain loop
can consume the domain list from the read-only DNS plan (requires `jq`):

```console
automx dns records --config /etc/automx/automx.conf --all-domains \
  --service-host autoconfig.example.net --format json \
| jq -r '.domains[]' \
| while IFS= read -r domain; do
    automx probe all --base-url "https://ua-auto-config.${domain}" \
      --email "probe@${domain}" --config /etc/automx/automx.conf \
      --domain "${domain}" || exit 1
  done
```
