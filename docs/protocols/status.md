# Protocol status and sources

This matrix records the exact source versions used by automx 3.0.0-beta.3. Internet-
Drafts are work in progress and must be re-reviewed before updating them.

| Surface | Implemented contract | Status |
| --- | --- | --- |
| Mail Autoconfig | `draft-ietf-mailmaint-autoconfig-06`, XML 1.2 | Internet-Draft |
| Autodiscover XML | MS-OXDSCLI Outlook 2006/2006a and MobileSync 2006 schemas | Microsoft Open Specification |
| Autodiscover v2 | EWS, ActiveSync, REST, Graph, OAB, Actions subset | Experimental, disabled by default |
| PACC | `draft-ietf-mailmaint-pacc-03` | Internet-Draft |
| Apple Mobileconfig | Apple Device Management configuration profiles | Published platform documentation |
| OAuth public clients | `draft-ietf-mailmaint-oauth-public-05` | Internet-Draft |
| OAuth registration/discovery | RFC 7591 and RFC 8414; OIDC Dynamic Client Registration 1.0 Errata 2 | Published specifications |

Primary sources:

- <https://www.ietf.org/archive/id/draft-ietf-mailmaint-autoconfig-06.html>
- <https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxdscli/>
- <https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-ascmd/>
- <https://datatracker.ietf.org/doc/draft-ietf-mailmaint-pacc/03/>
- <https://developer.apple.com/documentation/devicemanagement/configuring-multiple-devices-using-profiles>
- <https://datatracker.ietf.org/doc/draft-ietf-mailmaint-oauth-public/05/>
- <https://www.rfc-editor.org/rfc/rfc7591>
- <https://www.rfc-editor.org/rfc/rfc8414>
- <https://openid.net/specs/openid-connect-registration-1_0.html>

Autodiscover v2 has no comprehensive public normative specification. automx
therefore treats it as a configuration-only compatibility profile: request
values select an allowlisted protocol but can never select or construct a URL.
