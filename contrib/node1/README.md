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
- OAuth2 and TLS-protected password authentication;
- provider display names `Rößner-Network-Solutions` and `R.N.S.`.

The configured domain set is the exact live Mailstack relay-domain contract,
not merely a sample of DNS zones. The 2026-08-24 inventory found 33 forward
zones whose MX points at `mx.roessner-net.de`; a target-side PfxHTTP
`relay_domains` lookup accepted 26 of them. Those 26 domains are pinned in
`automx.conf`, the three Traefik host rules, `dns-plan.txt`, and a regression
test. The seven MX zones `roessner.cloud`, `dsgvo-roessner.de`, `nauthilus.de`,
`authserv.me`, `roessner.website`, `ra-roessner-merle.com`, and `authserv.net`
are intentionally excluded because the live mail service did not accept them.

The historical deployment contained the stale issuer
`https://oauth.authserv.me:4444`. The production profile instead uses the live
Nauthilus issuer `https://login.authserv.me`, whose discovery document exposes
the authorization and token endpoints, PKCE S256, public-client authentication,
and the configured scopes. The current discovery document has no
`registration_endpoint`; this prepares consumers to discover DCR from the
issuer as soon as a future Nauthilus rollout publishes it. automx never acts as
a registration endpoint, invents one, or publishes a client secret.

Autodiscover v2 remains disabled because this deployment has no configured
Exchange REST, EWS, ActiveSync, Graph, OAB, or Actions endpoint. The standard
Autoconfig, both Microsoft Autodiscover XML schemas, Mobileconfig, PACC, health,
and OpenAPI routes remain available.

## Apple configuration profiles

Open `https://autoconfig.roessner-net.de/mobileconfig` in Safari to request a
password-free Apple Mail configuration profile. The service root redirects to
the same form. It accepts only the mail address and an optional display name;
the device asks for account credentials when it first connects. The interface
offers English and German, plus persistent auto, light, and dark themes. Its
self-hosted CSS and JavaScript use no CDN or third-party browser service.

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

Never create a self-referential CNAME for the canonical service host. In the
`roessner-net.de` zone, `autoconfig.roessner-net.de` therefore retains its
direct A/AAAA records; only the other protocol host names are aliases.

After deployment, verify all protocols with synthetic addresses only:

```console
automx config validate --config automx.conf --domain roessner-net.de
automx probe all --base-url https://ua-auto-config.roessner-net.de \
  --email probe@roessner-net.de \
  --domain roessner-net.de \
  --config automx.conf
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
