# Production deployment example

This directory is a deliberately synthetic, public example for deploying automx
behind Traefik. Every hostname uses the reserved `.test` namespace. It contains
no operator-specific topology, account data, credentials, or production DNS.

## Prepare the image and configuration

1. Build and scan the image as documented in `../../docs/container.md`.
2. Push it to your registry and record its immutable digest.
3. Copy `automx.env.example` to `.env` and replace the digest placeholder.
4. Copy `automx.conf` and replace all `.test` values with your reviewed service
   contract.
5. Ensure the external Docker network named `edge` exists, or adapt that name
   consistently in `compose.yaml`.

The Compose service is unprivileged, read-only, capability-free, resource
bounded, health checked, and reachable only through the external proxy network.
The labels are examples: replace the ACME resolver and host rules for your
environment.

## Validate before deployment

```console
automx config validate --config automx.conf --domain example.test
automx dns records --config automx.conf --all-domains \
  --service-host automx.example.test
docker compose config --quiet
docker compose up -d --wait
automx probe all --base-url https://ua-auto-config.example.test \
  --email probe@example.test --domain example.test
```

`dns-plan.txt` is generated from the synthetic configuration and is included as
a reviewable example only. DNS commands are read-only: inspect the result, apply
it with your authoritative DNS workflow, and then verify the published view with
`automx dns check`. See `../../docs/cli.md` for per-domain and all-domain checks.

For PACC updates, publish the old and new TXT digests together during the cache
rollover described in `../../docs/migration.md`. Never update the HTTP
representation and its DNS digest independently.
