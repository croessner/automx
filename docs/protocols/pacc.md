# PACC-03 and DNS verification

automx implements `draft-ietf-mailmaint-pacc-03`, an Internet-Draft and work in
progress. It serves deterministic JSON at:

```text
https://ua-auto-config.example.com/.well-known/user-agent-configuration.json
```

The JSON contains only the protocol fields PACC defines. The configured SMTP
service is published under the PACC `submit` key. IMAP, POP3, and Submission
must use their PACC direct-TLS ports (993, 995, and 465). The draft currently
defines no usable direct-TLS port for ManageSieve, so automx rejects that PACC
profile rather than implying an interoperable endpoint. HTTP services use
absolute HTTPS URLs; WebDAV-family entries cannot be bare origins. OAuth
public-client metadata contains only a validated issuer.

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

Run `automx dns check` separately against every authoritative and desired
recursive resolver view to prove that the generated service alias and UAAC1
digest are complete and published. PACC permits multiple TXT RRs during a
configuration transition and ignores tag order, separator whitespace, a final
semicolon, and unknown future tags. The check therefore parses every TXT RR and
passes when any valid SHA-256 digest matches the exact locally rendered bytes.
Both DNS commands are read-only.
