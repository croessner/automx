from __future__ import annotations

from pathlib import Path

import pytest

from automx.configuration import ConfigurationError, ConfigurationRepository
from automx.domain import AuthenticationMethod, Protocol, TLSMode


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "automx.conf"
    path.write_text(content, encoding="utf-8")
    return path


def test_legacy_static_configuration_is_normalized_safely(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test

[DEFAULT]
account_name = Example Mail
account_name_short = Example

[global]
backend = static
smtp = yes
smtp_server = smtp.example.test
smtp_port = 587
smtp_encryption = starttls
smtp_auth = plaintext, oauth2
imap = yes
imap_server = imap.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = encrypted

[example.test]
backend = global
""",
    )

    profile = ConfigurationRepository.from_path(path).resolve("User@Example.Test")

    assert profile.provider == "example.test"
    assert profile.email_address == "User@example.test"
    assert profile.display_name == "Example Mail"
    assert [server.protocol for server in profile.servers] == [Protocol.SMTP, Protocol.IMAP]
    assert profile.servers[0].tls is TLSMode.STARTTLS
    assert profile.servers[0].authentication == (
        AuthenticationMethod.PASSWORD_CLEARTEXT,
        AuthenticationMethod.OAUTH2,
    )
    assert profile.servers[0].username == "%EMAILADDRESS%"
    assert profile.servers[1].authentication == (AuthenticationMethod.PASSWORD_ENCRYPTED,)


def test_plain_transport_requires_explicit_opt_in(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = static
pop = yes
pop_server = pop.example.test
pop_port = 110
pop_encryption = none
pop_auth = plaintext
""",
    )

    with pytest.raises(ConfigurationError, match="allow_insecure"):
        ConfigurationRepository.from_path(path).resolve("user@example.test")


def test_follow_cycle_is_rejected_with_section_path(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = static
follow = common
[common]
backend = static_append
follow = global
""",
    )

    with pytest.raises(ConfigurationError, match=r"global -> common -> global"):
        ConfigurationRepository.from_path(path).resolve("user@example.test")


def test_unknown_backend_and_unknown_authentication_are_rejected(tmp_path: Path) -> None:
    unknown_backend = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = magic
""",
    )
    with pytest.raises(ConfigurationError, match="unknown backend"):
        ConfigurationRepository.from_path(unknown_backend).resolve("user@example.test")

    unknown_auth = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = static
imap = yes
imap_server = imap.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = surprise
""",
    )
    with pytest.raises(ConfigurationError, match="authentication"):
        ConfigurationRepository.from_path(unknown_auth).resolve("user@example.test")


def test_oauth_and_url_protocols_are_typed(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = *
[global]
backend = static
oauth_issuer = https://identity.example.test
oauth_auth_url = https://identity.example.test/authorize
oauth_token_url = https://identity.example.test/token
oauth_scope = openid offline_access urn:ietf:params:oauth:scope:mail
oauth_client_id = automx-public-client
jmap = yes
jmap_url = https://mail.example.test/.well-known/jmap
""",
    )

    profile = ConfigurationRepository.from_path(path).resolve("user@tenant.example")

    assert profile.oauth is not None
    assert profile.oauth.client_secret is None
    assert profile.oauth.scopes[-1] == "urn:ietf:params:oauth:scope:mail"
    assert profile.servers[0].protocol is Protocol.JMAP
    assert profile.servers[0].url == "https://mail.example.test/.well-known/jmap"


def test_file_backend_keeps_documents_inside_config_directory(tmp_path: Path) -> None:
    document = tmp_path / "autoconfig.xml"
    document.write_text("<clientConfig/>", encoding="utf-8")
    path = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[example.test]
backend = file
autoconfig = autoconfig.xml
""",
    )

    profile = ConfigurationRepository.from_path(path).resolve("user@example.test")
    assert profile.static_documents[0].path == document.resolve()

    outside = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[example.test]
backend = file
autoconfig = ../outside.xml
""",
    )
    with pytest.raises(ConfigurationError, match="outside configuration directory"):
        ConfigurationRepository.from_path(outside).resolve("user@example.test")


def test_missing_or_invalid_mail_domain_does_not_fall_back(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = static
""",
    )
    repository = ConfigurationRepository.from_path(path)

    with pytest.raises(ConfigurationError, match="invalid email address"):
        repository.resolve("not-an-address")
    with pytest.raises(ConfigurationError, match="not configured"):
        repository.resolve("user@other.example")
