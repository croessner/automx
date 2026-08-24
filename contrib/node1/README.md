# node1 production deployment

This directory defines the production-shaped automx deployment for
`node1.roessner-net.de`. It intentionally contains no credentials. The image is
pulled from the private registry and pinned by digest in the untracked `.env`
file on node1.

## Service contract

The profile preserves the working account settings from the retired PHP/Nginx
deployment:

- IMAPS at `mail.roessner-net.de:993`;
- SMTPS at `mail.roessner-net.de:465`;
- full email address as the authentication identity;
- provider display names `Rößner-Network-Solutions` and `R.N.S.`.

The historical deployment advertised the issuer
`https://oauth.authserv.me:4444`, but that issuer was unreachable during the
migration. OAuth is therefore not advertised by the production profile. Add
the verified issuer, endpoints, scopes, and `oauth2` authentication method only
after the issuer discovery document and DCR policy are operational again.
automx never acts as a registration endpoint and never publishes a client
secret.

Autodiscover v2 remains disabled because this deployment has no configured
Exchange REST, EWS, ActiveSync, Graph, OAB, or Actions endpoint. The standard
Autoconfig, both Microsoft Autodiscover XML schemas, Mobileconfig, PACC, health,
and OpenAPI routes remain available.

## Deployment

Copy `compose.yaml` and `automx.conf` to `/srv/docker/automx`. Create a root-only
`.env` from `automx.env.example` and replace the placeholder with the immutable
digest published by the private registry:

```console
install -m 0600 automx.env.example .env
docker compose config -q
docker compose pull automx
docker compose up -d --wait automx
```

The container has no host port, joins only the external `rnsweb` network, runs
as UID/GID 10001, drops all capabilities, uses a read-only root filesystem, and
has bounded process, memory, CPU, log, and temporary-file resources.

## DNS and verification

Use `automx dns records` to render a read-only plan for each configured domain.
The node1 rollout keeps direct A/AAAA records on the canonical
`autoconfig.roessner-net.de` host. Autoconfig, Autodiscover, and PACC service
names use CNAME aliases, while every SRV record targets the canonical A/AAAA
host directly. `dns-plan.txt` contains the exact PACC TXT digest rendered from
this configuration and is checked by the test suite.

After deployment, verify all protocols with synthetic addresses only:

```console
automx config validate --config automx.conf --domain roessner-net.de
automx probe all --base-url https://autoconfig.roessner-net.de \
  --email-address probe@roessner-net.de \
  --domain roessner-net.de \
  --config automx.conf \
  --pacc-base-url https://ua-auto-config.roessner-net.de
```

Repeat the probe for every configured mail domain and use that domain's
Autoconfig, Autodiscover, and PACC host names. Verify the authoritative answers
from both `ns1.roessner-net.de` and `ns2.roessner-net.de` before relying on a
public-recursive result.

## Rollback

Before migration, create a root-only archive of `/srv/docker/autoconfig`, record
its SHA-256 digest, extract it into a temporary directory, and run
`docker compose config -q` against the extracted file. Also snapshot the exact
affected PowerDNS RRsets. To roll back, stop the `automx` project, restore the
archived directory at `/srv/docker/autoconfig`, restore the DNS snapshot, and
start the old project with the original Compose project name. Keep the scoped
Zabbix Maintenance active until the old synthetic HTTP probes pass.
