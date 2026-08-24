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
  -> protocol-specific renderer
  -> framework Response
```

`app.py` composes routes and error mappings. `requests.py` enforces media types,
body limits, and safe XML parsing. `configuration.py` reads compatible INI
configuration and resolves one profile per request. `backends.py` isolates
optional LDAP, SQL, and script lookups. `domain.py` contains strict frozen
Pydantic models. Renderers cannot access HTTP state or backend credentials.

The modular CLI in `automx.commands` consumes the same repository, renderer,
and app factory. Consequently PACC DNS digests are computed over the same bytes
as the HTTP response, and offline OpenAPI exports describe the actual routes.

## Trust boundaries

- Administrators control the INI file and optional backend configuration.
- Email addresses, query values, XML, and forms are untrusted request input.
- Dynamic backend results are untrusted until expanded into validated domain
  models.
- OAuth authorization-server metadata is published as a discovery pointer;
  automx is not an authorization server or dynamic registration endpoint.
- Autodiscover v2 URLs come only from configuration, never from request input.

Access logging records method, path, and status only. Query strings, request
bodies, cookies, authorization headers, and resolved account data are excluded.
