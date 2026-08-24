"""Password-free Apple configuration-profile renderer."""

from __future__ import annotations

import plistlib
import re
import uuid

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


def _identifier(profile: AccountProfile) -> str:
    value = f"org.automx.mail.{profile.provider}.{profile.email_address}"
    return re.sub(r"[^A-Za-z0-9.-]", ".", value)


def render_mobileconfig(profile: AccountProfile, *, common_name: str | None = None) -> bytes:
    """Render a deterministic Apple Mail configuration profile without credentials."""

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
        "PayloadContent": [mail_payload],
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
