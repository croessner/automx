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

## DNS records

```console
automx dns records --config /etc/automx/automx.conf \
  --domain example.com --service-host automx.example.net --format zone
```

The command emits Autoconfig and Autodiscover aliases, the Autodiscover SRV
record, the PACC service alias, and the exact UAAC1 TXT digest. `--format json`
is suitable for infrastructure tooling. This command is always read-only and
has no provider credentials or apply mode.

## Remote probes

Use `probe health`, `probe autoconfig`, `probe autodiscover`, `probe pacc`, or
`probe all`. HTTPS is required unless `--allow-insecure-http` is explicitly used
for an isolated local stack. Redirects are not followed, responses are bounded,
and XML is parsed without DTD or entities.

`--include-experimental` adds Autodiscover v2. `--config PATH` makes the PACC
probe compare remote bytes with the local renderer. For HTTP Basic protection,
put `username:password` in an environment variable and pass only its name with
`--basic-auth-env`; never place a password on the command line.
