# Configuration reference

automx uses UTF-8 INI files. `[automx]` and at least one domain or wildcard are
required:

```ini
[automx]
provider = example.test
domains = example.test
autodiscover_v2 = no

[global]
backend = static
imap = yes
imap_server = imap.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = oauth2, plaintext
smtp = yes
smtp_server = smtp.example.test
smtp_port = 465
smtp_encryption = ssl
smtp_auth = oauth2, plaintext
```

`provider` is the provider DNS name. `domains` is a comma- or whitespace-
separated allowlist; `*` permits any syntactically valid address. A matching
domain section wins over `[global]`. `backend = global` delegates to the global
section. `follow` continues with another named section; cycles and chains deeper
than 16 sections fail validation.

## TCP services

Prefixes are `imap`, `pop`, `smtp`, and `managesieve`. Each enabled service
requires `_server`, `_port`, `_encryption`, and `_auth`. Encryption is `ssl` or
`starttls`. `none`/`plain` is rejected unless the section explicitly sets
`allow_insecure = yes`.

Authentication values may be ordered with commas or spaces: `plaintext`,
`encrypted`, `gssapi`, `ntlm`, `tls-client-cert`, `oauth2`, `none`,
`smtp-after-pop`, and `client-ip-address`. The safe username default is
`%EMAILADDRESS%`; override it with `<service>_auth_identity`.

PACC-03 publishes the configured SMTP submission endpoint as `submit` and
requires fixed direct-TLS ports: IMAP 993, POP3 995, and Submission 465. The
current draft lists ManageSieve but has no registered direct-TLS port, so automx
fails closed instead of emitting an unusable PACC entry. Other valid ports can
still be represented in Autoconfig, Autodiscover, and Mobileconfig. PACC
CalDAV, CardDAV, and WebDAV URLs must identify a context path rather than a bare
origin.

## URL services

Prefixes are `jmap`, `ews`, `activesync`, `caldav`, `carddav`, `webdav`,
`rest`, `graph`, `oab`, and `actions`. Each enabled service requires an absolute
HTTPS `<service>_url`. Optional keys are `<service>_auth`,
`<service>_auth_identity`, and `<service>_server_location`.

Only EWS, ActiveSync, REST, Graph, OAB, and Actions are eligible for the
experimental Autodiscover v2 response allowlist.

Mail Autoconfig 1.2 also publishes configured EWS, ActiveSync, and Graph
endpoints as `incomingServer` entries. REST, OAB, and Actions remain limited to
the explicitly enabled experimental Autodiscover v2 surface. ManageSieve is
published as the root-level `setupServer` element.

## OAuth public-client metadata

```ini
oauth_issuer = https://identity.example.test/
oauth_auth_url = https://identity.example.test/authorize
oauth_token_url = https://identity.example.test/token
oauth_scope = openid offline_access urn:ietf:params:oauth:scope:mail
# oauth_client_id = optional-pre-registered-public-client
```

The issuer must use HTTPS and have no query or fragment. Client secrets are
rejected. See [OAuth and DCR](protocols/oauth-dcr.md).

## Dynamic backends

`script`, `sql`, and `ldap` backends return named variables referenced as
`${attribute}` by static options. Append variants retain an already selected
service. Script commands run without a shell, with a bounded timeout and output.
SQL statements must use SQLAlchemy bound parameters such as `:emailaddress`;
legacy `%s` interpolation is rejected. LDAP certificate validation defaults to
`demand`. Install only the required extra: `automx[sql]` or `automx[ldap]`.

`backend = file` accepts relative `autoconfig`, `autodiscover`, and
`mobileconfig` paths rooted at the configuration directory. Files are bounded to
1 MiB and validated before serving; XML cannot contain DTDs/entities and static
Mobileconfig profiles cannot contain password keys. Absolute or escaping paths
are rejected.

Run `automx config validate --config PATH --domain DOMAIN` before deployment.
The synthetic [E2E configuration](../contrib/e2e/automx.conf) demonstrates every
current service family without real credentials.
