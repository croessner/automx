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
