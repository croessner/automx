# OAuth, OIDC discovery, and dynamic client registration

automx publishes enough information for a capable mail client to locate an
OAuth authorization server. It is not an authorization server and does not
implement a dynamic client registration endpoint.

Mail Autoconfig 1.2 can publish a pre-registered public `clientID` or direct the
client to the configured issuer. PACC publishes only the issuer. The client then
uses RFC 8414 or OpenID Connect Discovery to obtain authorization, token, and
optional `registration_endpoint` metadata. If no suitable client identifier was
pre-registered, the client may use RFC 7591/OIDC Dynamic Client Registration at
the authorization server.

The public-client profile is expected to support Authorization Code, Refresh
Token, PKCE `S256`, `token_endpoint_auth_method=none`, issuer identification,
and the protocol-specific DPoP rules of `draft-ietf-mailmaint-oauth-public-06`. Deployments
must configure mail/contact/calendar scopes appropriate to their authorization
server. automx does not infer scopes or endpoints and never publishes a client
secret.

Administrators must verify authorization-server discovery and registration
policy separately. An issuer URL accepted by automx is a syntactic configuration
contract, not proof that the external server is reachable or interoperable.

## OAuth public -06 deployment responsibilities

The source is [draft-ietf-mailmaint-oauth-public-06, published 2026-09-16](https://www.ietf.org/archive/id/draft-ietf-mailmaint-oauth-public-06.html),
an Internet-Draft, not an RFC. Its native-client profile does not cover browser
or server-side web applications. Updating automx discovery metadata alone does
not establish conformance of a deployment to the entire profile.

- **Issuer publication (automx):** Section 3.2 requires an HTTPS URI without
  user information, query, fragment, dot path segments, or percent-encoded
  unreserved path characters. automx rejects these instead of normalizing them.
  Valid issuer spelling is retained exactly, including a trailing path slash,
  which -06 permits. Invalid percent escapes and non-URI characters are also
  rejected. Endpoint discovery and exact issuer comparison belong to the client.
- **Discovery (client and servers):** Clients fetch RFC 8414 metadata with the
  specified OIDC fallback and do not follow metadata redirects. Resource servers
  expose the issuer through RFC 9728 metadata for HTTP or the failed
  OAUTHBEARER response for IMAP/POP/SMTP. automx remains only a publisher of
  configured endpoints and issuer information.
- **Resource binding (client and authorization server):** Sections 3.2, 3.4,
  and 3.6 define complete `protected_resources` metadata when required,
  component-wise URL matching, hostname resource indicators for non-HTTP
  services, and restrictions on where tokens may be sent. Cross-domain hosting
  needs particular care: the authorization server must advertise the permitted
  resources; clients must apply the draft's registrable-domain fallback only
  when that metadata is absent. These are authorization-server metadata fields,
  not extra Autoconfig or PACC fields.
- **DPoP (client and authorization server):** Section 3.8 distinguishes HTTP
  from SASL services. DPoP-bound access tokens cannot be used with IMAP, POP,
  or SMTP OAUTHBEARER. A mixed client may use bearer tokens throughout or follow
  the specified resource-separated token flow. It must not register
  `dpop_bound_access_tokens=true` for that mixed flow, must check token types,
  and must support DPoP nonce handling when using DPoP.
- **Scopes (deployment):** Section 3.9 requires a conforming server to support
  the interoperable scopes for the services it offers. The profile defines
  `urn:ietf:params:oauth:scope:mail`, `urn:ietf:params:oauth:scope:contacts`, and
  `urn:ietf:params:oauth:scope:calendars`. Configure the actual supported scopes;
  automx preserves configured scopes and cannot grant or verify their meaning.
  Private scopes remain possible but do not substitute for these requirements
  when claiming full profile conformance.

For an upgrade, validate each domain's configuration and test the native login,
refresh, and resource-access flows against the external servers separately.
Existing valid issuer metadata produces unchanged document bytes. Correcting
an invalid issuer changes PACC bytes and requires updating its DNS digest.

## DAV discovery across formats

| Format | CalDAV and CardDAV | OAuth publication |
| --- | --- | --- |
| Mail Autoconfig 1.2 (`draft-ietf-mailmaint-autoconfig-06`) | Root-level `calendar` and `addressbook` elements | Per-service `OAuth2` authentication and shared `oAuth2` metadata |
| PACC (`draft-ietf-mailmaint-pacc-03`) | `protocols.caldav` and `protocols.carddav` URLs | Provider-wide `authentication.oauth-public.issuer`; `password: false` for OAuth-only configurations |
| Apple Mobileconfig | Generic CalDAV and CardDAV account payloads | No documented arbitrary OAuth issuer/client configuration in these payloads |
| Microsoft Autodiscover Outlook/MobileSync XML | No CalDAV/CardDAV mapping in the implemented schemas | Exchange/ActiveSync discovery is not DAV discovery |
| Experimental Autodiscover v2 | No CalDAV/CardDAV mapping in the supported allowlist | No invented DAV protocol extension |

The pinned Autoconfig and PACC versions were checked against the IETF
Datatracker on 2026-09-29 and remain Internet-Drafts. Both formats already
publish DAV endpoints independently of the Mobileconfig renderer. PACC
authentication describes the provider as a whole; clients must still determine
the authentication mechanisms of each service.

OIDC provides identity on top of OAuth; DAV requests use the OAuth access token,
not the OIDC ID token. The client and DAV server must support the corresponding
OAuth flow and access tokens. An OIDC login for a service's web interface alone
does not prove that its DAV endpoint accepts bearer tokens. Configure the
issuer and scopes for all intended services and verify the complete client
login and DAV access flow separately.

## Apple profile limitations

The published Apple schemas for
[CalDAV](https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.caldav.account.yaml)
and [CardDAV](https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.carddav.account.yaml)
provide username/password, server, port, TLS and principal-URL fields, but no
generic OAuth issuer, client ID, scopes or token-endpoint fields. This limits
what automx can configure through these payloads; it is not a claim that every
Apple account type or application lacks OAuth support.

The same boundary applies to generic IMAP/POP/SMTP provisioning: Apple's
[Mail payload](https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.mail.managed.yaml)
and newer
[declarative Mail configuration](https://github.com/apple/device-management/blob/release/declarative/declarations/configurations/account.mail.yaml)
list password and legacy authentication methods but no OAuth method. OAuth
fields documented for Exchange payloads cannot be transferred to these mail
or DAV payloads. Autoconfig and PACC still publish OAuth-only IMAP/SMTP with
the configured issuer; an OAuth-capable client is required to use it.

With password-capable mail and OAuth-only DAV, Mobileconfig contains the mail
account and omits the DAV accounts. With `oauth2, http-basic` DAV authentication,
it includes password-based DAV accounts because that alternative was explicitly
configured. With OAuth-only IMAP or SMTP, the existing generic mail renderer
rejects Mobileconfig with HTTP 422 (`unsupported_configuration`). It never
fabricates a password fallback for an OAuth-only mail service.

For an entirely OAuth-based deployment, use a client that implements the
published Autoconfig/PACC OAuth contracts and supports bearer authentication for
DAV. Adding unsupported keys to a Mobileconfig profile cannot supply that
client functionality. The omission must not be worked around by advertising
password authentication that the service does not actually support.

Apple also documents `CardDAVPrincipalURL` as unavailable on macOS. Successful
behavior observed on a particular macOS release is not a documented guarantee
for arbitrary CardDAV paths or future releases.
