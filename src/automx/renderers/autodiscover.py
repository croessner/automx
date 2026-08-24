"""Strict Microsoft Autodiscover XML parsing and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import cast
from urllib.parse import urlsplit

from lxml import etree

from automx.domain import AccountProfile, AuthenticationMethod, Protocol, Server, TLSMode
from automx.renderers.common import expand_username

OUTLOOK_REQUEST_NAMESPACE = (
    "http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006"
)
MOBILE_REQUEST_NAMESPACE = (
    "http://schemas.microsoft.com/exchange/autodiscover/mobilesync/requestschema/2006"
)
RESPONSE_NAMESPACE = "http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006"
OUTLOOK_RESPONSE_NAMESPACE = (
    "http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a"
)
MOBILE_RESPONSE_NAMESPACE = (
    "http://schemas.microsoft.com/exchange/autodiscover/mobilesync/responseschema/2006"
)


class AutodiscoverSchema(StrEnum):
    OUTLOOK = "outlook"
    MOBILE = "mobile"


@dataclass(frozen=True, slots=True)
class AutodiscoverRequest:
    email_address: str
    schema: AutodiscoverSchema


class AutodiscoverRequestError(RuntimeError):
    """A Microsoft protocol-level request error."""

    def __init__(self, error_code: int, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class AutodiscoverRenderError(RuntimeError):
    """The profile cannot satisfy the requested response schema."""


def _qualified(namespace: str, name: str) -> etree.QName:
    return etree.QName(namespace, name)


def _element(namespace: str, name: str, *, root: bool = False) -> etree._Element:
    return etree.Element(
        _qualified(namespace, name),
        nsmap={None: namespace} if root else None,
    )


def _subelement(parent: etree._Element, namespace: str, name: str) -> etree._Element:
    return etree.SubElement(parent, _qualified(namespace, name))


def _text(parent: etree._Element, namespace: str, name: str, value: str) -> etree._Element:
    element = _subelement(parent, namespace, name)
    element.text = value
    return element


def parse_autodiscover_request(root: etree._Element) -> AutodiscoverRequest:
    """Parse only the two exact Microsoft request namespaces and shapes."""

    root_name = etree.QName(root)
    namespace = root_name.namespace
    if root_name.localname != "Autodiscover" or namespace not in {
        OUTLOOK_REQUEST_NAMESPACE,
        MOBILE_REQUEST_NAMESPACE,
    }:
        raise AutodiscoverRequestError(600, "Invalid Request")
    request_nodes = root.findall(_qualified(namespace, "Request"))
    if len(request_nodes) != 1 or len(root) != 1:
        raise AutodiscoverRequestError(600, "Invalid Request")
    request_node = request_nodes[0]
    email_nodes = request_node.findall(_qualified(namespace, "EMailAddress"))
    schema_nodes = request_node.findall(_qualified(namespace, "AcceptableResponseSchema"))
    if len(email_nodes) != 1 or len(schema_nodes) != 1 or len(request_node) != 2:
        raise AutodiscoverRequestError(600, "Invalid Request")
    email_address = (email_nodes[0].text or "").strip()
    response_schema = (schema_nodes[0].text or "").strip()
    if not email_address:
        raise AutodiscoverRequestError(600, "Invalid Request")

    if namespace == OUTLOOK_REQUEST_NAMESPACE and response_schema == OUTLOOK_RESPONSE_NAMESPACE:
        schema = AutodiscoverSchema.OUTLOOK
    elif namespace == MOBILE_REQUEST_NAMESPACE and response_schema == MOBILE_RESPONSE_NAMESPACE:
        schema = AutodiscoverSchema.MOBILE
    elif response_schema not in {OUTLOOK_RESPONSE_NAMESPACE, MOBILE_RESPONSE_NAMESPACE}:
        raise AutodiscoverRequestError(601, "Provider Not Available")
    else:
        raise AutodiscoverRequestError(600, "Invalid Request")
    return AutodiscoverRequest(email_address=email_address, schema=schema)


def render_autodiscover_error(
    error_code: int,
    message: str,
    *,
    response_namespace: str = RESPONSE_NAMESPACE,
) -> bytes:
    """Render a deterministic framework error without echoing request data."""

    root = _element(RESPONSE_NAMESPACE, "Autodiscover", root=True)
    response = _subelement(root, response_namespace, "Response")
    error = _subelement(response, response_namespace, "Error")
    error.set("Time", "00:00:00.0000000")
    error.set("Id", "0")
    _text(error, response_namespace, "ErrorCode", str(error_code))
    _text(error, response_namespace, "Message", message)
    _subelement(error, response_namespace, "DebugData")
    return _serialize(root)


def render_outlook(profile: AccountProfile) -> bytes:
    """Render Outlook account settings with one Protocol element per endpoint."""

    preferred_order = (Protocol.IMAP, Protocol.POP3, Protocol.SMTP, Protocol.EWS)
    supported = tuple(
        server
        for protocol in preferred_order
        for server in profile.servers
        if server.protocol is protocol
    )
    if not supported:
        raise AutodiscoverRenderError("no Outlook service is configured")
    namespace = OUTLOOK_RESPONSE_NAMESPACE
    root = _element(RESPONSE_NAMESPACE, "Autodiscover", root=True)
    response = _subelement(root, namespace, "Response")
    user = _subelement(response, namespace, "User")
    _text(user, namespace, "DisplayName", profile.display_name or profile.email_address)
    _text(user, namespace, "AutoDiscoverSMTPAddress", profile.email_address)
    account = _subelement(response, namespace, "Account")
    _text(account, namespace, "AccountType", "email")
    _text(account, namespace, "Action", "settings")
    for server in supported:
        _outlook_protocol(account, namespace, server, profile)
    return _serialize(root)


def _outlook_protocol(
    parent: etree._Element,
    namespace: str,
    server: Server,
    profile: AccountProfile,
) -> None:
    protocol = _subelement(parent, namespace, "Protocol")
    if server.protocol is Protocol.EWS:
        if server.url is None:  # enforced by the model
            raise AutodiscoverRenderError("EWS service has no URL")
        hostname = urlsplit(server.url).hostname
        if hostname is None:  # enforced by the model
            raise AutodiscoverRenderError("EWS service URL has no host")
        _text(protocol, namespace, "Type", "EXPR")
        _text(protocol, namespace, "Server", hostname)
        _text(protocol, namespace, "EwsUrl", server.url)
        return

    _text(protocol, namespace, "Type", server.protocol.value.upper())
    location = server.host if server.host is not None else server.url
    if location is None:  # enforced by the model
        raise AutodiscoverRenderError("Autodiscover service has no location")
    _text(protocol, namespace, "Server", location)
    if server.port is not None:
        _text(protocol, namespace, "Port", str(server.port))
    _text(protocol, namespace, "DomainRequired", "off")
    _text(protocol, namespace, "LoginName", expand_username(profile, server.username))
    _text(
        protocol,
        namespace,
        "SPA",
        "on" if AuthenticationMethod.NTLM in server.authentication else "off",
    )
    if server.tls is not None:
        encryption = {
            TLSMode.SSL: "SSL",
            TLSMode.STARTTLS: "TLS",
            TLSMode.PLAIN: "None",
        }[server.tls]
        _text(protocol, namespace, "Encryption", encryption)
    auth_required = any(
        method is not AuthenticationMethod.NONE for method in server.authentication
    )
    _text(protocol, namespace, "AuthRequired", "on" if auth_required else "off")


def render_mobile(profile: AccountProfile) -> bytes:
    """Render the MobileSync response for the configured ActiveSync endpoint."""

    active_sync = next(
        (server for server in profile.servers if server.protocol is Protocol.ACTIVESYNC),
        None,
    )
    if active_sync is None or active_sync.url is None:
        raise AutodiscoverRenderError("no ActiveSync URL is configured")
    namespace = MOBILE_RESPONSE_NAMESPACE
    root = _element(RESPONSE_NAMESPACE, "Autodiscover", root=True)
    response = _subelement(root, namespace, "Response")
    _text(response, namespace, "Culture", "en:us")
    user = _subelement(response, namespace, "User")
    _text(user, namespace, "DisplayName", profile.display_name or profile.email_address)
    _text(user, namespace, "EMailAddress", profile.email_address)
    action = _subelement(response, namespace, "Action")
    settings = _subelement(action, namespace, "Settings")
    server = _subelement(settings, namespace, "Server")
    _text(server, namespace, "Type", "MobileSync")
    _text(server, namespace, "Url", active_sync.url)
    _text(server, namespace, "Name", urlsplit(active_sync.url).hostname or active_sync.url)
    return _serialize(root)


def _serialize(root: etree._Element) -> bytes:
    return cast(
        bytes,
        etree.tostring(
            root,
            encoding="UTF-8",
            xml_declaration=True,
            pretty_print=True,
        ),
    )
