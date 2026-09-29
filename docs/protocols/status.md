# Protocol status and sources

This matrix records the exact source versions used by automx 3.0.0-beta.3. Internet-
Drafts are work in progress and must be re-reviewed before updating them.

| Surface | Implemented contract | Status |
| --- | --- | --- |
| Mail Autoconfig | `draft-ietf-mailmaint-autoconfig-06`, XML 1.2 | Internet-Draft |
| Autodiscover XML | MS-OXDSCLI 24.1 (2025-08-19), Outlook 2006/2006a; MS-ASCMD 28.0 (2025-05-20), MobileSync 2006 | Microsoft Open Specification |
| Autodiscover v2 | EWS, ActiveSync, REST, Graph, OAB, Actions subset | Experimental, disabled by default |
| PACC | `draft-ietf-mailmaint-pacc-03` | Internet-Draft |
| Apple Mobileconfig | Apple Device Management configuration profiles | Published platform documentation |
| OAuth public clients | `draft-ietf-mailmaint-oauth-public-06` | Internet-Draft |
| OAuth registration/discovery | RFC 7591 and RFC 8414; OIDC Dynamic Client Registration 1.0 Errata 2 | Published specifications |

Primary sources:

- <https://www.ietf.org/archive/id/draft-ietf-mailmaint-autoconfig-06.html>
- <https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxdscli/78530279-d042-4eb0-a1f4-03b18143cd19>
- <https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-ascmd/1a3490f1-afe1-418a-aa92-6f630036d65a>
- <https://datatracker.ietf.org/doc/draft-ietf-mailmaint-pacc/03/>
- <https://developer.apple.com/documentation/devicemanagement/configuring-multiple-devices-using-profiles>
- <https://datatracker.ietf.org/doc/draft-ietf-mailmaint-oauth-public/06/>
- <https://www.rfc-editor.org/rfc/rfc7591>
- <https://www.rfc-editor.org/rfc/rfc8414>
- <https://openid.net/specs/openid-connect-registration-1_0.html>

Autodiscover v2 has no comprehensive public normative specification. automx
therefore treats it as a configuration-only compatibility profile: request
values select an allowlisted protocol but can never select or construct a URL.

## Source review on 2026-09-29

Autoconfig -06 and PACC -03 remain the current published Internet-Draft
revisions. OAuth public clients -06 was published on 2026-09-16. automx
implements its issuer-publication boundary; it does not implement the native
client, authorization server, or protected resource server flow. See
[OAuth deployment responsibilities](oauth-dcr.md#oauth-public-06-deployment-responsibilities).
The OAuth update does not change the Autoconfig or PACC response structure.

Microsoft document revisions above identify the source baseline, not a change
to XML namespace years or a claim to implement all Exchange functionality.
The [MS-OXDSCLI 24.1 change log](https://learn.microsoft.com/fr-fr/openspecs/exchange_server_protocols/ms-oxdscli/96b5aaf2-4f93-45fe-bd14-dbf487e5fbc8)
adds `OwnerSmtpAddress` to `AlternativeMailbox` and clarifies Exchange-specific
capability, OWA authentication, and Type behavior. automx does not emit those
alternative-mailbox or OWA structures or implement MAPI capability negotiation.
The [Outlook response XSD](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxdscli/9c9284b4-244d-4692-93a0-f5c44bf153ad),
[MobileSync response envelope](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-ascmd/45d24b78-559e-4aa9-8294-3e40261dda23),
and [MobileSync settings schema](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-ascmd/5d3826fb-a081-4b13-bd8c-1d97fe1b0a1e)
retain the namespaces used by automx. This source update requires no additional
response fields for its configured endpoint subset; existing positive and
negative Autodiscover contracts remain applicable.

Apple publishes evolving platform schemas rather than a numbered protocol
release. The Mail, CalDAV, and CardDAV schemas linked in
[Apple profile limitations](oauth-dcr.md#apple-profile-limitations) were checked
on the same date; they still do not define generic OAuth issuer/client fields.
RFC 7591, RFC 8414, and OIDC Registration Errata 2 remain the referenced
registration/discovery specifications.
