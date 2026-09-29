"""Validated, immutable account-configuration domain objects."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Protocol(StrEnum):
    """Protocols that automx can publish."""

    IMAP = "imap"
    POP3 = "pop3"
    SMTP = "smtp"
    MANAGESIEVE = "managesieve"
    JMAP = "jmap"
    EWS = "ews"
    ACTIVESYNC = "activesync"
    CALDAV = "caldav"
    CARDDAV = "carddav"
    WEBDAV = "webdav"
    REST = "rest"
    GRAPH = "graph"
    OAB = "oab"
    ACTIONS = "actions"


class TLSMode(StrEnum):
    """Transport-security modes used by TCP based protocols."""

    SSL = "ssl"
    STARTTLS = "starttls"
    PLAIN = "plain"


class AuthenticationMethod(StrEnum):
    """Authentication alternatives supported by the protocol renderers."""

    PASSWORD_CLEARTEXT = "password-cleartext"  # noqa: S105 - protocol token
    PASSWORD_ENCRYPTED = "password-encrypted"  # noqa: S105 - protocol token
    GSSAPI = "GSSAPI"
    NTLM = "NTLM"
    TLS_CLIENT_CERT = "TLS-client-cert"
    OAUTH2 = "OAuth2"
    HTTP_BASIC = "http-basic"
    HTTP_DIGEST = "http-digest"
    NONE = "none"
    SMTP_AFTER_POP = "SMTP-after-POP"
    CLIENT_IP_ADDRESS = "client-IP-address"


TCP_PROTOCOLS = frozenset(
    {Protocol.IMAP, Protocol.POP3, Protocol.SMTP, Protocol.MANAGESIEVE}
)
URL_PROTOCOLS = frozenset(set(Protocol) - TCP_PROTOCOLS)


def validate_https_url(value: str, *, field_name: str) -> str:
    """Validate an unambiguous public HTTPS URL without embedded credentials."""

    parts = urlsplit(value)
    if parts.scheme.lower() != "https" or not parts.hostname:
        msg = f"{field_name} must be an absolute HTTPS URL"
        raise ValueError(msg)
    if parts.username is not None or parts.password is not None:
        msg = f"{field_name} must not contain user information"
        raise ValueError(msg)
    try:
        port = parts.port
    except ValueError as exc:
        msg = f"{field_name} port must be an integer between 1 and 65535"
        raise ValueError(msg) from exc
    if port is not None and not 1 <= port <= 65535:
        msg = f"{field_name} port must be an integer between 1 and 65535"
        raise ValueError(msg)
    return value


class ImmutableModel(BaseModel):
    """Shared strict and immutable Pydantic configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class OAuthConfiguration(ImmutableModel):
    """OAuth public-client metadata published by automx.

    automx is not an authorization server. In particular, it never publishes a
    client secret or invents a dynamic-registration endpoint.
    """

    issuer: str = Field(strict=True)
    authorization_url: str | None = None
    token_url: str | None = None
    scopes: tuple[str, ...] = ()
    client_id: str | None = None
    client_secret: str | None = Field(default=None, repr=False, exclude=True)

    @field_validator("issuer", mode="before")
    @classmethod
    def validate_issuer_syntax(cls, value: object) -> object:
        """Reject ambiguous issuer spelling before Pydantic or URL parsing can trim it.

        Draft-ietf-mailmaint-oauth-public-06 section 3.2 requires exact issuer
        identity. Validate without decoding or normalizing the published value.
        """
        if not isinstance(value, str):
            return value
        if not re.fullmatch(r"[A-Za-z0-9:/\[\]@!$&'()*+,;=._~%\-]+", value):
            raise ValueError("issuer must be an ASCII HTTPS URI without query or fragment")
        if re.search(r"%(?![0-9A-Fa-f]{2})", value):
            raise ValueError("issuer contains invalid percent-encoding")
        validate_https_url(value, field_name="issuer")
        path = urlsplit(value).path
        if not re.fullmatch(r"[A-Za-z0-9/:@!$&'()*+,;=._~%\-]*", path):
            raise ValueError("issuer contains invalid URI path characters")
        if any(segment in {".", ".."} for segment in path.split("/")):
            raise ValueError("issuer must not contain dot path segments")
        for encoded in re.findall(r"%([0-9A-Fa-f]{2})", path):
            if re.fullmatch(r"[A-Za-z0-9._~\-]", chr(int(encoded, 16))):
                raise ValueError("issuer must not percent-encode unreserved path characters")
        return value

    @model_validator(mode="after")
    def validate_oauth_metadata(self) -> OAuthConfiguration:
        for field_name, value in (
            ("authorization_url", self.authorization_url),
            ("token_url", self.token_url),
        ):
            if value is not None:
                validate_https_url(value, field_name=field_name)
        if self.client_secret is not None:
            msg = "public client secrets are not supported"
            raise ValueError(msg)
        if len(set(self.scopes)) != len(self.scopes):
            msg = "OAuth scopes must be unique"
            raise ValueError(msg)
        return self


class Server(ImmutableModel):
    """A single typed protocol endpoint."""

    protocol: Protocol
    host: str | None = None
    url: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    tls: TLSMode | None = None
    authentication: tuple[AuthenticationMethod, ...] = ()
    username: str = "%EMAILADDRESS%"
    default: bool = False
    server_location: str | None = None

    @model_validator(mode="after")
    def validate_endpoint_shape(self) -> Server:
        if self.protocol in TCP_PROTOCOLS:
            if self.host is None or self.url is not None or self.port is None or self.tls is None:
                msg = "TCP protocols require host, port and tls, and do not accept url"
                raise ValueError(msg)
            if any(char.isspace() for char in self.host) or "/" in self.host:
                msg = "host must be a hostname or address without whitespace or path"
                raise ValueError(msg)
        elif self.url is None or self.host is not None or self.port is not None or self.tls is not None:
            msg = "URL protocols require only url"
            raise ValueError(msg)
        else:
            validate_https_url(self.url, field_name="url")

        if len(set(self.authentication)) != len(self.authentication):
            msg = "authentication alternatives must be unique"
            raise ValueError(msg)
        return self


class StaticDocument(ImmutableModel):
    """A compatibility document selected by the legacy file backend."""

    kind: str
    path: Path


class AccountProfile(ImmutableModel):
    """Complete, renderer-independent configuration for one account."""

    provider: str
    domains: tuple[str, ...]
    email_address: str
    display_name: str | None = None
    display_name_short: str | None = None
    servers: tuple[Server, ...] = ()
    oauth: OAuthConfiguration | None = None
    static_documents: tuple[StaticDocument, ...] = ()
    help_url: str | None = None
    help_email: str | None = None

    @model_validator(mode="after")
    def validate_profile(self) -> AccountProfile:
        if "@" not in self.email_address:
            msg = "email_address must contain a domain"
            raise ValueError(msg)
        email_domain = self.email_address.rsplit("@", 1)[1].lower()
        configured_domains = {domain.lower() for domain in self.domains}
        if email_domain not in configured_domains:
            msg = "email_address domain is not present in domains"
            raise ValueError(msg)
        if not self.provider or any(char.isspace() for char in self.provider):
            msg = "provider must be a non-empty DNS name"
            raise ValueError(msg)
        if self.help_url is not None:
            validate_https_url(self.help_url, field_name="help_url")
        return self
