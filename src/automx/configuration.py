"""Strict, compatible INI loading and account-profile resolution."""

from __future__ import annotations

import configparser
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from pydantic import ValidationError

from automx.backends import DYNAMIC_BACKENDS, BackendContext, BackendError
from automx.domain import (
    AccountProfile,
    AuthenticationMethod,
    OAuthConfiguration,
    Protocol,
    Server,
    StaticDocument,
    TLSMode,
)
from automx.mobileconfig_signing import MobileconfigSigner, MobileconfigSigningError


class ConfigurationError(RuntimeError):
    """The configuration or a requested profile is invalid."""


_TRUE = frozenset({"1", "yes", "true", "on"})
_FALSE = frozenset({"0", "no", "false", "off"})
_VARIABLE = re.compile(r"\$\{([^}]+)}")
_TCP_SERVICES: tuple[tuple[str, Protocol], ...] = (
    ("smtp", Protocol.SMTP),
    ("imap", Protocol.IMAP),
    ("pop", Protocol.POP3),
    ("managesieve", Protocol.MANAGESIEVE),
)
_URL_SERVICES: tuple[tuple[str, Protocol], ...] = (
    ("jmap", Protocol.JMAP),
    ("ews", Protocol.EWS),
    ("activesync", Protocol.ACTIVESYNC),
    ("caldav", Protocol.CALDAV),
    ("carddav", Protocol.CARDDAV),
    ("webdav", Protocol.WEBDAV),
    ("rest", Protocol.REST),
    ("graph", Protocol.GRAPH),
    ("oab", Protocol.OAB),
    ("actions", Protocol.ACTIONS),
)
_AUTHENTICATION = {
    "plaintext": AuthenticationMethod.PASSWORD_CLEARTEXT,
    "cleartext": AuthenticationMethod.PASSWORD_CLEARTEXT,
    "password-cleartext": AuthenticationMethod.PASSWORD_CLEARTEXT,
    "encrypted": AuthenticationMethod.PASSWORD_ENCRYPTED,
    "password-encrypted": AuthenticationMethod.PASSWORD_ENCRYPTED,
    "gssapi": AuthenticationMethod.GSSAPI,
    "ntlm": AuthenticationMethod.NTLM,
    "tls-client-cert": AuthenticationMethod.TLS_CLIENT_CERT,
    "oauth2": AuthenticationMethod.OAUTH2,
    "http-basic": AuthenticationMethod.HTTP_BASIC,
    "http-digest": AuthenticationMethod.HTTP_DIGEST,
    "none": AuthenticationMethod.NONE,
    "smtp-after-pop": AuthenticationMethod.SMTP_AFTER_POP,
    "client-ip-address": AuthenticationMethod.CLIENT_IP_ADDRESS,
}


def _items(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.replace(",", " ").split() if item)


def _boolean(value: str, *, option: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ConfigurationError(f"{option} must be a boolean")


@dataclass(slots=True)
class _ProfileBuilder:
    provider: str
    domain: str
    email_address: str
    display_name: str | None = None
    display_name_short: str | None = None
    servers: dict[Protocol, Server] = field(default_factory=dict)
    oauth: OAuthConfiguration | None = None
    static_documents: dict[str, StaticDocument] = field(default_factory=dict)
    help_url: str | None = None
    help_email: str | None = None
    variables: dict[str, str] = field(default_factory=dict)

    def profile(self) -> AccountProfile:
        return AccountProfile(
            provider=self.provider,
            domains=(self.domain,),
            email_address=self.email_address,
            display_name=self.display_name,
            display_name_short=self.display_name_short,
            servers=tuple(self.servers.values()),
            oauth=self.oauth,
            static_documents=tuple(self.static_documents.values()),
            help_url=self.help_url,
            help_email=self.help_email,
        )


class ConfigurationRepository:
    """Immutable source configuration with per-request profile resolution."""

    _MAX_SECTION_DEPTH = 16

    def __init__(self, parser: configparser.ConfigParser, path: Path) -> None:
        self._parser = parser
        self.path = path
        self.base_directory = path.parent.resolve()
        if not parser.has_section("automx"):
            raise ConfigurationError("missing [automx] section")
        self.provider = parser.get("automx", "provider", fallback="").strip().lower()
        self.domains = tuple(domain.lower() for domain in _items(
            parser.get("automx", "domains", fallback="")
        ))
        if not self.provider:
            raise ConfigurationError("[automx] provider is required")
        if not self.domains:
            raise ConfigurationError("[automx] domains is required")
        self.autodiscover_v2_enabled = _boolean(
            parser.get("automx", "autodiscover_v2", fallback="no"),
            option="autodiscover_v2",
        )
        self.mobileconfig_signer = self._mobileconfig_signer()

    def _mobileconfig_signer(self) -> MobileconfigSigner | None:
        enabled = _boolean(
            self._parser.get("automx", "mobileconfig_sign", fallback="no"),
            option="mobileconfig_sign",
        )
        option_names = (
            "mobileconfig_signing_certificate",
            "mobileconfig_signing_key",
            "mobileconfig_signing_key_password_file",
        )
        configured = {
            name: self._parser.get("automx", name, fallback="").strip()
            for name in option_names
        }
        if not enabled:
            if any(configured.values()):
                raise ConfigurationError(
                    "mobileconfig signing options require mobileconfig_sign=yes"
                )
            return None
        if not configured["mobileconfig_signing_certificate"]:
            raise ConfigurationError("mobileconfig signing certificate is required")
        if not configured["mobileconfig_signing_key"]:
            raise ConfigurationError("mobileconfig signing key is required")

        def signing_path(name: str) -> Path | None:
            value = configured[name]
            if not value:
                return None
            candidate = Path(value).expanduser()
            if not candidate.is_absolute():
                candidate = self.base_directory / candidate
            return candidate.resolve()

        certificate_path = signing_path("mobileconfig_signing_certificate")
        key_path = signing_path("mobileconfig_signing_key")
        if certificate_path is None or key_path is None:
            raise ConfigurationError("mobileconfig signing identity is incomplete")
        try:
            return MobileconfigSigner.from_files(
                certificate_path,
                key_path,
                signing_path("mobileconfig_signing_key_password_file"),
            )
        except MobileconfigSigningError as exc:
            raise ConfigurationError(str(exc)) from exc

    @classmethod
    def from_path(cls, path: str | Path) -> ConfigurationRepository:
        config_path = Path(path).expanduser().resolve()
        if not config_path.is_file():
            raise ConfigurationError(f"configuration file does not exist: {config_path}")
        parser = configparser.ConfigParser(
            interpolation=None,
            strict=True,
            empty_lines_in_values=False,
        )
        try:
            with config_path.open(encoding="utf-8") as config_file:
                parser.read_file(config_file)
        except (OSError, UnicodeError, configparser.Error) as exc:
            raise ConfigurationError(f"cannot read configuration: {config_path}") from exc
        return cls(parser, config_path)

    def resolve(self, email_address: str) -> AccountProfile:
        try:
            validated = validate_email(
                email_address,
                check_deliverability=False,
                allow_smtputf8=False,
                globally_deliverable=False,
                test_environment=True,
            )
        except EmailNotValidError as exc:
            raise ConfigurationError("invalid email address") from exc
        normalized = validated.normalized
        domain = normalized.rsplit("@", 1)[1].lower()
        if "*" not in self.domains and domain not in self.domains:
            raise ConfigurationError(f"domain {domain!r} is not configured")

        builder = _ProfileBuilder(
            provider=self.provider,
            domain=domain,
            email_address=normalized,
        )
        section = domain if self._parser.has_section(domain) else "global"
        if not self._parser.has_section(section):
            raise ConfigurationError(f"missing [{section}] section")
        self._resolve_section(section, builder, path=())
        try:
            return builder.profile()
        except ValidationError as exc:
            raise ConfigurationError("resolved account profile is invalid") from exc

    def _resolve_section(
        self,
        section: str,
        builder: _ProfileBuilder,
        *,
        path: tuple[str, ...],
        forced_backend: str | None = None,
    ) -> None:
        if section in path:
            cycle = " -> ".join((*path, section))
            raise ConfigurationError(f"configuration section cycle: {cycle}")
        if len(path) >= self._MAX_SECTION_DEPTH:
            raise ConfigurationError("configuration section depth exceeds 16")
        if not self._parser.has_section(section):
            raise ConfigurationError(f"missing configuration section [{section}]")

        options = dict(self._parser.items(section, raw=True))
        backend = (forced_backend or options.get("backend", "")).strip().lower()
        append = backend.endswith("_append")
        backend_name = backend.removesuffix("_append")
        next_path = (*path, section)

        if backend_name == "global":
            self._resolve_section("global", builder, path=next_path)
            return
        if backend_name == "static":
            self._apply_static(options, builder, append=append)
        elif backend_name == "file":
            self._apply_files(options, builder, append=append)
            self._apply_static(options, builder, append=append)
        elif backend_name in DYNAMIC_BACKENDS:
            context = BackendContext(
                email_address=builder.email_address,
                local_part=builder.email_address.rsplit("@", 1)[0],
                domain=builder.domain,
            )
            try:
                variables = DYNAMIC_BACKENDS[backend_name].resolve(options, context)
            except BackendError as exc:
                raise ConfigurationError(f"{backend_name} backend failed") from exc
            builder.variables.update(variables)
            self._apply_static(options, builder, append=append)
        else:
            raise ConfigurationError(f"unknown backend {backend!r} in [{section}]")

        follow = options.get("follow", "").strip()
        if follow:
            self._resolve_section(self._expand(follow, builder), builder, path=next_path)

    def _apply_static(
        self, options: Mapping[str, str], builder: _ProfileBuilder, *, append: bool
    ) -> None:
        expanded = {name: self._expand(value, builder) for name, value in options.items()}
        builder.display_name = expanded.get("account_name", builder.display_name)
        builder.display_name_short = expanded.get("account_name_short", builder.display_name_short)
        builder.help_url = expanded.get("help_url", builder.help_url)
        builder.help_email = expanded.get("help_email", builder.help_email)

        oauth_issuer = expanded.get("oauth_issuer")
        if oauth_issuer:
            try:
                builder.oauth = OAuthConfiguration(
                    issuer=oauth_issuer,
                    authorization_url=expanded.get("oauth_auth_url"),
                    token_url=expanded.get("oauth_token_url"),
                    scopes=_items(expanded.get("oauth_scope", "")),
                    client_id=expanded.get("oauth_client_id"),
                    client_secret=expanded.get("oauth_client_secret"),
                )
            except ValidationError as exc:
                raise ConfigurationError("invalid OAuth configuration") from exc

        allow_insecure = _boolean(
            expanded.get("allow_insecure", "no"), option="allow_insecure"
        )
        for prefix, protocol in _TCP_SERVICES:
            if not _boolean(expanded.get(prefix, "no"), option=prefix):
                continue
            server = self._tcp_server(prefix, protocol, expanded, allow_insecure=allow_insecure)
            if append and protocol in builder.servers:
                continue
            builder.servers[protocol] = server

        for prefix, protocol in _URL_SERVICES:
            if not _boolean(expanded.get(prefix, "no"), option=prefix):
                continue
            url = expanded.get(f"{prefix}_url")
            if not url:
                raise ConfigurationError(f"{prefix}_url is required when {prefix}=yes")
            authentication = self._authentication(expanded.get(f"{prefix}_auth", ""))
            try:
                server = Server(
                    protocol=protocol,
                    url=url,
                    authentication=authentication,
                    username=expanded.get(f"{prefix}_auth_identity", "%EMAILADDRESS%"),
                    server_location=expanded.get(f"{prefix}_server_location"),
                )
            except ValidationError as exc:
                raise ConfigurationError(f"invalid {prefix} service") from exc
            if append and protocol in builder.servers:
                continue
            builder.servers[protocol] = server

    def _tcp_server(
        self,
        prefix: str,
        protocol: Protocol,
        options: Mapping[str, str],
        *,
        allow_insecure: bool,
    ) -> Server:
        host = options.get(f"{prefix}_server", "")
        port_text = options.get(f"{prefix}_port", "")
        if not host or not port_text:
            raise ConfigurationError(f"{prefix}_server and {prefix}_port are required")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ConfigurationError(f"{prefix}_port must be an integer") from exc

        encryption = options.get(f"{prefix}_encryption", "").strip().lower()
        tls = {
            "ssl": TLSMode.SSL,
            "starttls": TLSMode.STARTTLS,
            "none": TLSMode.PLAIN,
            "plain": TLSMode.PLAIN,
        }.get(encryption)
        if tls is None:
            raise ConfigurationError(f"invalid {prefix}_encryption")
        if tls is TLSMode.PLAIN and not allow_insecure:
            raise ConfigurationError(
                f"{prefix}_encryption={encryption} requires allow_insecure=yes"
            )
        authentication = self._authentication(options.get(f"{prefix}_auth", ""))
        if not authentication:
            raise ConfigurationError(f"{prefix}_auth is required")
        try:
            return Server(
                protocol=protocol,
                host=host,
                port=port,
                tls=tls,
                authentication=authentication,
                username=options.get(f"{prefix}_auth_identity", "%EMAILADDRESS%"),
                default=_boolean(options.get(f"{prefix}_default", "no"), option=f"{prefix}_default"),
            )
        except ValidationError as exc:
            raise ConfigurationError(f"invalid {prefix} service") from exc

    @staticmethod
    def _authentication(value: str) -> tuple[AuthenticationMethod, ...]:
        result: list[AuthenticationMethod] = []
        for item in _items(value):
            method = _AUTHENTICATION.get(item.lower())
            if method is None:
                raise ConfigurationError(f"unknown authentication method {item!r}")
            result.append(method)
        if len(set(result)) != len(result):
            raise ConfigurationError("authentication methods must be unique")
        return tuple(result)

    def _apply_files(
        self, options: Mapping[str, str], builder: _ProfileBuilder, *, append: bool
    ) -> None:
        for kind in ("autoconfig", "autodiscover", "mobileconfig"):
            value = options.get(kind)
            if not value:
                continue
            candidate = (self.base_directory / self._expand(value, builder)).resolve()
            if not candidate.is_relative_to(self.base_directory):
                raise ConfigurationError(f"{kind} file is outside configuration directory")
            if not candidate.is_file():
                raise ConfigurationError(f"{kind} file does not exist")
            if append and kind in builder.static_documents:
                continue
            builder.static_documents[kind] = StaticDocument(kind=kind, path=candidate)

    @staticmethod
    def _expand(value: str, builder: _ProfileBuilder) -> str:
        local_part = builder.email_address.rsplit("@", 1)[0]
        result = value.replace("%u", local_part).replace("%d", builder.domain).replace(
            "%s", builder.email_address
        )
        return _VARIABLE.sub(lambda match: builder.variables.get(match.group(1), ""), result)
