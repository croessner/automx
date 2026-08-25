# Architecture

automx is a pure ASGI application. FastAPI owns HTTP routing and OpenAPI;
Uvicorn is the production server. There is no WSGI adapter or import-time
configuration singleton.

The request flow is deliberately one-way:

```text
HTTP request
  -> bounded request parser
  -> ConfigurationRepository
  -> immutable AccountProfile and Server models
  -> shared document service
  -> validated static document or protocol-specific renderer
  -> framework Response
```

Optional Mobileconfig signing is composed in the shared document service after
profile rendering and before the framework response. The signer loads bounded,
permission-checked key material once from explicit administrator configuration,
uses in-process RSA/SHA-256 CMS, and verifies the attached DER result before it
can leave the service. Renderers never read signing files or credentials.

`app.py` composes routes and error mappings. `requests.py` enforces media types,
body limits, and safe XML parsing. `configuration.py` reads compatible INI
configuration and resolves one profile per request. `backends.py` isolates
optional LDAP, SQL, and script lookups. `domain.py` contains strict frozen
Pydantic models. `documents.py` is the single composition point used by ASGI,
local rendering, PACC digest generation, and DNS planning. Renderers cannot
access HTTP state or backend credentials.

The modular CLI in `automx.commands` consumes the same repository, document
service, and app factory. `automx.dns_contracts` isolates normalized, bounded DNS
resolution behind an injectable resolver protocol; it neither reads service
configuration nor mutates a provider. Consequently PACC DNS digests are
computed over the same bytes as the HTTP response, and offline OpenAPI exports
describe the actual routes.

## Trust boundaries

- Administrators control the INI file and optional backend configuration.
- Mobileconfig signing keys and password files are administrator-controlled
  secrets with owner-only filesystem permissions; no request can select them.
- Email addresses, query values, XML, and forms are untrusted request input.
- Dynamic backend results are untrusted until expanded into validated domain
  models.
- OAuth authorization-server metadata is published as a discovery pointer;
  automx is not an authorization server or dynamic registration endpoint.
- Autodiscover v2 URLs come only from configuration, never from request input.
- DNS checks compare only generated required owners through a bounded read-only
  resolver. They have no provider credentials, zone-transfer, or apply path.

Access logging records method, path, and status only. Query strings, request
bodies, cookies, authorization headers, and resolved account data are excluded.
