"""PACC-03 JSON rendering and UAAC1 digest generation."""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import urlsplit

from automx.domain import AccountProfile, AuthenticationMethod, Protocol, TLSMode


class PaccRenderError(RuntimeError):
    """A profile cannot be represented safely under PACC-03."""


_TEXT_PROTOCOLS: dict[Protocol, tuple[int, frozenset[TLSMode]]] = {
    Protocol.IMAP: (993, frozenset({TLSMode.SSL})),
    Protocol.POP3: (995, frozenset({TLSMode.SSL})),
    Protocol.SMTP: (465, frozenset({TLSMode.SSL})),
}
_PACC_PROTOCOL_NAMES = {Protocol.SMTP: "submit"}
_HTTP_PROTOCOLS = frozenset(
    {Protocol.JMAP, Protocol.CALDAV, Protocol.CARDDAV, Protocol.WEBDAV}
)
_PASSWORD_METHODS = frozenset(
    {
        AuthenticationMethod.PASSWORD_CLEARTEXT,
        AuthenticationMethod.PASSWORD_ENCRYPTED,
        AuthenticationMethod.HTTP_BASIC,
        AuthenticationMethod.HTTP_DIGEST,
        AuthenticationMethod.NTLM,
        AuthenticationMethod.GSSAPI,
    }
)


def _validate_provider_text(value: str | None, *, name: str, maximum: int) -> str:
    if value is None or not value or len(value) > maximum:
        raise PaccRenderError(f"{name} is missing or exceeds {maximum} characters")
    if not value.isprintable() or any(part == "" for part in value.split(" ")):
        raise PaccRenderError(f"{name} contains control characters or excessive whitespace")
    return value


def render_pacc(profile: AccountProfile) -> bytes:
    """Render compact deterministic JSON matching draft-ietf-mailmaint-pacc-03."""

    protocols: dict[str, dict[str, str]] = {}
    skipped_managesieve = False
    for server in profile.servers:
        if server.protocol in _TEXT_PROTOCOLS:
            expected_port, accepted_tls = _TEXT_PROTOCOLS[server.protocol]
            if server.port != expected_port or server.tls not in accepted_tls:
                raise PaccRenderError(
                    f"{server.protocol.value} must use its PACC default TLS port"
                )
            if server.host is None:  # enforced by the model
                raise PaccRenderError(f"{server.protocol.value} has no host")
            protocol_name = _PACC_PROTOCOL_NAMES.get(server.protocol, server.protocol.value)
            protocols.setdefault(protocol_name, {"host": server.host})
        elif server.protocol == Protocol.MANAGESIEVE:
            skipped_managesieve = True
        elif server.protocol in _HTTP_PROTOCOLS:
            if server.url is None:  # enforced by the model
                raise PaccRenderError(f"{server.protocol.value} has no URL")
            parts = urlsplit(server.url)
            if parts.port is not None:
                raise PaccRenderError(f"{server.protocol.value} URL must not use an explicit port")
            if server.protocol in {Protocol.CALDAV, Protocol.CARDDAV, Protocol.WEBDAV} and (
                not parts.path or parts.path == "/"
            ):
                raise PaccRenderError(
                    f"{server.protocol.value} URL must identify a WebDAV context path"
                )
            protocols.setdefault(server.protocol.value, {"url": server.url})
    if not protocols:
        if skipped_managesieve:
            raise PaccRenderError(
                "managesieve has no registered PACC-03 direct-TLS port"
            )
        raise PaccRenderError("at least one PACC protocol is required")

    provider: dict[str, str] = {
        "name": _validate_provider_text(
            profile.display_name,
            name="provider name",
            maximum=60,
        )
    }
    if profile.display_name_short is not None:
        provider["shortName"] = _validate_provider_text(
            profile.display_name_short,
            name="provider short name",
            maximum=20,
        )
    info: dict[str, object] = {"provider": provider}
    if profile.help_url is not None:
        info["help"] = {"documentation": profile.help_url}

    password_supported = any(
        any(authentication in _PASSWORD_METHODS for authentication in server.authentication)
        for server in profile.servers
    )
    authentication: dict[str, object] = {"password": password_supported}
    if profile.oauth is not None:
        authentication["oauth-public"] = {"issuer": profile.oauth.issuer}

    document = {
        "protocols": protocols,
        "authentication": authentication,
        "info": info,
    }
    return json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def pacc_digest_record(body: bytes) -> str:
    """Return the DNS TXT RDATA for the exact decoded HTTP body bytes."""

    digest = base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")
    return f"v=UAAC1; a=sha256; d={digest}"
