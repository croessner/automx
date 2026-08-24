"""Mail Autoconfig XML 1.2 renderer.

The output contract follows draft-ietf-mailmaint-autoconfig-06. The draft is
work in progress and is intentionally named in project documentation.
"""

from __future__ import annotations

from typing import cast

from lxml import etree

from automx.domain import (
    AccountProfile,
    AuthenticationMethod,
    Protocol,
    Server,
    TLSMode,
)


class AutoconfigRenderError(RuntimeError):
    """A valid domain profile cannot satisfy the Autoconfig contract."""


_SOCKET_TYPE = {
    TLSMode.SSL: "SSL",
    TLSMode.STARTTLS: "STARTTLS",
    TLSMode.PLAIN: "plain",
}
_GLOBAL_ELEMENTS = {
    Protocol.CALDAV: "calendar",
    Protocol.CARDDAV: "addressbook",
    Protocol.WEBDAV: "fileShare",
    Protocol.MANAGESIEVE: "setupServer",
}
_INCOMING_PROTOCOLS = frozenset(
    {
        Protocol.IMAP,
        Protocol.POP3,
        Protocol.JMAP,
        Protocol.EWS,
        Protocol.ACTIVESYNC,
        Protocol.GRAPH,
    }
)
_PROTOCOL_TYPES = {Protocol.ACTIVESYNC: "activeSync"}
_PUBLISHED_PROTOCOLS = _INCOMING_PROTOCOLS | {Protocol.SMTP} | frozenset(_GLOBAL_ELEMENTS)


def _text(parent: etree._Element, name: str, value: str) -> etree._Element:
    element = etree.SubElement(parent, name)
    element.text = value
    return element


def _authentication(parent: etree._Element, method: AuthenticationMethod) -> None:
    value = method.value
    system: str | None = None
    if method is AuthenticationMethod.HTTP_BASIC:
        value = "Basic"
        system = "http"
    elif method is AuthenticationMethod.HTTP_DIGEST:
        value = "Digest"
        system = "http"
    element = _text(parent, "authentication", value)
    if system is not None:
        element.set("system", system)


def _server(parent: etree._Element, server: Server) -> None:
    tag = "outgoingServer" if server.protocol is Protocol.SMTP else "incomingServer"
    element = etree.SubElement(
        parent,
        tag,
        type=_PROTOCOL_TYPES.get(server.protocol, server.protocol.value),
    )
    if server.host is not None:
        _text(element, "hostname", server.host)
        if server.port is None or server.tls is None:  # enforced by the model
            raise AutoconfigRenderError("TCP endpoint is incomplete")
        _text(element, "port", str(server.port))
        _text(element, "socketType", _SOCKET_TYPE[server.tls])
    elif server.url is not None:
        _text(element, "url", server.url)
    else:  # enforced by the model
        raise AutoconfigRenderError("server has no location")
    for authentication in server.authentication:
        _authentication(element, authentication)
    _text(element, "username", server.username)


def _global_service(root: etree._Element, server: Server) -> None:
    name = _GLOBAL_ELEMENTS[server.protocol]
    element = etree.SubElement(root, name, type=server.protocol.value)
    if server.url is not None:
        _text(element, "url", server.url)
    elif server.host is not None:
        _text(element, "hostname", server.host)
        if server.port is None or server.tls is None:  # enforced by the model
            raise AutoconfigRenderError("global TCP endpoint is incomplete")
        _text(element, "port", str(server.port))
        _text(element, "socketType", _SOCKET_TYPE[server.tls])
    else:  # enforced by the model
        raise AutoconfigRenderError("global service has no location")
    for authentication in server.authentication:
        _authentication(element, authentication)
    _text(element, "username", server.username)


def render_autoconfig(profile: AccountProfile) -> bytes:
    """Render a deterministic UTF-8 Autoconfig 1.2 document."""

    uses_oauth = any(
        server.protocol in _PUBLISHED_PROTOCOLS
        and AuthenticationMethod.OAUTH2 in server.authentication
        for server in profile.servers
    )
    if uses_oauth and profile.oauth is None:
        raise AutoconfigRenderError("OAuth authentication requires OAuth metadata")
    if uses_oauth and profile.oauth is not None and not profile.oauth.scopes:
        raise AutoconfigRenderError("OAuth authentication requires at least one scope")

    root = etree.Element("clientConfig", version="1.2")
    provider = etree.SubElement(root, "emailProvider", id=profile.provider)
    for domain in profile.domains:
        _text(provider, "domain", domain)
    if profile.display_name is not None:
        _text(provider, "displayName", profile.display_name)
    if profile.display_name_short is not None:
        _text(provider, "displayShortName", profile.display_name_short)

    for server in profile.servers:
        if server.protocol in _INCOMING_PROTOCOLS or server.protocol is Protocol.SMTP:
            _server(provider, server)

    if profile.help_url is not None:
        documentation = etree.SubElement(provider, "documentation", url=profile.help_url)
        _text(documentation, "descr", "Mail account configuration").set("lang", "en")

    for server in profile.servers:
        if server.protocol in _GLOBAL_ELEMENTS:
            _global_service(root, server)

    if profile.oauth is not None:
        oauth = etree.SubElement(root, "oAuth2")
        if profile.oauth.authorization_url is not None:
            _text(oauth, "authURL", profile.oauth.authorization_url)
        if profile.oauth.token_url is not None:
            _text(oauth, "tokenURL", profile.oauth.token_url)
        _text(oauth, "issuer", profile.oauth.issuer)
        if profile.oauth.scopes:
            _text(oauth, "scope", " ".join(profile.oauth.scopes))
        if profile.oauth.client_id is not None:
            _text(oauth, "clientID", profile.oauth.client_id)

    return cast(
        bytes,
        etree.tostring(
            root,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        ),
    )
