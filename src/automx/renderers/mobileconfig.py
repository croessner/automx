"""Password-free Apple configuration-profile renderer."""

from __future__ import annotations

import plistlib
import re
import uuid
from urllib.parse import urlsplit

from automx.domain import AccountProfile, AuthenticationMethod, Protocol, Server, TLSMode
from automx.renderers.common import expand_username


class MobileconfigRenderError(RuntimeError):
    """A profile cannot be represented as an Apple Mail payload."""


_AUTHENTICATION = {
    AuthenticationMethod.PASSWORD_CLEARTEXT: "EmailAuthPassword",
    AuthenticationMethod.PASSWORD_ENCRYPTED: "EmailAuthCRAMMD5",
    AuthenticationMethod.NTLM: "EmailAuthNTLM",
    AuthenticationMethod.NONE: "EmailAuthNone",
}

_DAV_ACCOUNTS = (
    (Protocol.CALDAV, "com.apple.caldav.account", "CalDAV", "calendar"),
    (Protocol.CARDDAV, "com.apple.carddav.account", "CardDAV", "contacts"),
)
_DAV_PASSWORD_AUTHENTICATION = frozenset(
    {
        AuthenticationMethod.HTTP_BASIC,
        AuthenticationMethod.HTTP_DIGEST,
        AuthenticationMethod.PASSWORD_CLEARTEXT,
        AuthenticationMethod.PASSWORD_ENCRYPTED,
    }
)


def _server(profile: AccountProfile, *protocols: Protocol) -> Server:
    for protocol in protocols:
        for server in profile.servers:
            if server.protocol is protocol:
                return server
    names = " or ".join(protocol.value for protocol in protocols)
    raise MobileconfigRenderError(f"mobileconfig requires {names}")


def _authentication(server: Server) -> str:
    for method in server.authentication:
        result = _AUTHENTICATION.get(method)
        if result is not None:
            return result
    raise MobileconfigRenderError(
        f"{server.protocol.value} has no authentication supported by Apple Mail profiles"
    )


def _dav_payloads(
    profile: AccountProfile, identifier: str, namespace: uuid.UUID, organization: str
) -> list[dict[str, object]]:
    """Build password-free CalDAV/CardDAV account payloads.

    Apple's generic DAV payload schemas expose no OAuth issuer or client
    configuration. Services without a password alternative are omitted only
    from this format; Autoconfig and PACC retain their OAuth-capable endpoints.
    """

    payloads: list[dict[str, object]] = []
    for protocol, payload_type, prefix, label in _DAV_ACCOUNTS:
        server = next((item for item in profile.servers if item.protocol is protocol), None)
        if server is None or server.url is None:
            continue
        if server.authentication and not _DAV_PASSWORD_AUTHENTICATION.intersection(
            server.authentication
        ):
            continue
        url = urlsplit(server.url)
        port = url.port
        payloads.append(
            {
                f"{prefix}AccountDescription": organization,
                f"{prefix}HostName": url.hostname,
                f"{prefix}Port": 443 if port is None else port,
                f"{prefix}PrincipalURL": server.url,
                f"{prefix}UseSSL": True,
                f"{prefix}Username": expand_username(profile, server.username),
                "PayloadDescription": f"Configure a {prefix} {label} account.",
                "PayloadDisplayName": f"{prefix} Account ({organization})",
                "PayloadIdentifier": f"{identifier}.{protocol.value}",
                "PayloadOrganization": profile.provider,
                "PayloadType": payload_type,
                "PayloadUUID": str(uuid.uuid5(namespace, protocol.value)),
                "PayloadVersion": 1,
            }
        )
    return payloads


def _identifier(profile: AccountProfile) -> str:
    value = f"org.automx.mail.{profile.provider}.{profile.email_address}"
    return re.sub(r"[^A-Za-z0-9.-]", ".", value)


def render_mobileconfig(profile: AccountProfile, *, common_name: str | None = None) -> bytes:
    """Render a deterministic Apple configuration profile without credentials.

    The profile always contains the mail account and adds CalDAV and CardDAV
    accounts for configured password-authenticated DAV services.
    """

    incoming = _server(profile, Protocol.IMAP, Protocol.POP3)
    outgoing = _server(profile, Protocol.SMTP)
    if incoming.host is None or incoming.port is None or incoming.tls is None:
        raise MobileconfigRenderError("incoming server is incomplete")
    if outgoing.host is None or outgoing.port is None or outgoing.tls is None:
        raise MobileconfigRenderError("outgoing server is incomplete")

    organization = profile.display_name or profile.provider
    account_name = common_name or profile.display_name or profile.email_address
    identifier = _identifier(profile)
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, identifier)
    mail_uuid = str(uuid.uuid5(namespace, "mail"))
    profile_uuid = str(uuid.uuid5(namespace, "profile"))
    mail_type = "EmailTypeIMAP" if incoming.protocol is Protocol.IMAP else "EmailTypePOP"

    mail_payload: dict[str, object] = {
        "EmailAccountDescription": organization,
        "EmailAccountName": account_name,
        "EmailAccountType": mail_type,
        "EmailAddress": profile.email_address,
        "IncomingMailServerAuthentication": _authentication(incoming),
        "IncomingMailServerHostName": incoming.host,
        "IncomingMailServerPortNumber": incoming.port,
        "IncomingMailServerUseSSL": incoming.tls is not TLSMode.PLAIN,
        "IncomingMailServerUsername": expand_username(profile, incoming.username),
        "OutgoingMailServerAuthentication": _authentication(outgoing),
        "OutgoingMailServerHostName": outgoing.host,
        "OutgoingMailServerPortNumber": outgoing.port,
        "OutgoingMailServerUseSSL": outgoing.tls is not TLSMode.PLAIN,
        "OutgoingMailServerUsername": expand_username(profile, outgoing.username),
        "OutgoingPasswordSameAsIncomingPassword": True,
        "PayloadDescription": "Configure an email account.",
        "PayloadDisplayName": f"Mail Account ({organization})",
        "PayloadIdentifier": f"{identifier}.mail",
        "PayloadOrganization": profile.provider,
        "PayloadType": "com.apple.mail.managed",
        "PayloadUUID": mail_uuid,
        "PayloadVersion": 1,
        "PreventAppSheet": False,
        "PreventMove": False,
        "SMIMEEnabled": False,
    }
    result: dict[str, object] = {
        "PayloadContent": [
            mail_payload,
            *_dav_payloads(profile, identifier, namespace, organization),
        ],
        "PayloadDescription": "automx mail configuration",
        "PayloadDisplayName": organization,
        "PayloadIdentifier": identifier,
        "PayloadOrganization": profile.provider,
        "PayloadRemovalDisallowed": False,
        "PayloadType": "Configuration",
        "PayloadUUID": profile_uuid,
        "PayloadVersion": 1,
    }
    return plistlib.dumps(result, fmt=plistlib.FMT_XML, sort_keys=True)
