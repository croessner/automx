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
and the DPoP requirements of `draft-ietf-mailmaint-oauth-public-05`. Deployments
must configure mail/contact/calendar scopes appropriate to their authorization
server. automx does not infer scopes or endpoints and never publishes a client
secret.

Administrators must verify authorization-server discovery and registration
policy separately. An issuer URL accepted by automx is a syntactic configuration
contract, not proof that the external server is reachable or interoperable.

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
