# PACC-02 and DNS verification

automx implements `draft-ietf-mailmaint-pacc-02`, an Internet-Draft and work in
progress. It serves deterministic JSON at:

```text
https://ua-auto-config.example.com/.well-known/user-agent-configuration.json
```

The JSON contains only the protocol fields PACC defines. IMAP, POP3, and SMTP
must use their PACC implicit-TLS ports (993, 995, and 465). HTTP services use
absolute HTTPS URLs. OAuth public-client metadata contains only a validated
issuer.

PACC discovery is complete only when `_ua-auto-config.example.com` publishes a
TXT record containing the SHA-256 digest of the decoded HTTP response bytes:

```console
automx pacc digest --config /etc/automx/automx.conf --domain example.com
```

The result has this shape:

```text
v=UAAC1; a=sha256; d=<base64-sha256>
```

Generate the full read-only DNS plan with `automx dns records`. Any byte change
to the JSON document changes the digest and requires a DNS update. Validate the
deployed body against local configuration with:

```console
automx probe pacc --base-url https://ua-auto-config.example.com \
  --email probe@example.com --config /etc/automx/automx.conf \
  --domain example.com
```
