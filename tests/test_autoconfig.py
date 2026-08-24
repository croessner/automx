from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from automx.app import create_app
from automx.domain import (
    AccountProfile,
    AuthenticationMethod,
    OAuthConfiguration,
    Protocol,
    Server,
    TLSMode,
)
from automx.renderers.autoconfig import AutoconfigRenderError, render_autoconfig


def rich_profile() -> AccountProfile:
    return AccountProfile(
        provider="example.test",
        domains=("example.test",),
        email_address="user@example.test",
        display_name="Example Mail",
        display_name_short="Example",
        servers=(
            Server(
                protocol=Protocol.IMAP,
                host="imap.example.test",
                port=993,
                tls=TLSMode.SSL,
                authentication=(
                    AuthenticationMethod.OAUTH2,
                    AuthenticationMethod.PASSWORD_CLEARTEXT,
                ),
            ),
            Server(
                protocol=Protocol.POP3,
                host="pop.example.test",
                port=995,
                tls=TLSMode.SSL,
                authentication=(AuthenticationMethod.PASSWORD_CLEARTEXT,),
            ),
            Server(
                protocol=Protocol.SMTP,
                host="smtp.example.test",
                port=587,
                tls=TLSMode.STARTTLS,
                authentication=(
                    AuthenticationMethod.OAUTH2,
                    AuthenticationMethod.SMTP_AFTER_POP,
                    AuthenticationMethod.CLIENT_IP_ADDRESS,
                ),
                default=True,
            ),
            Server(
                protocol=Protocol.JMAP,
                url="https://mail.example.test/jmap",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
            Server(
                protocol=Protocol.ACTIVESYNC,
                url="https://mail.example.test/Microsoft-Server-ActiveSync",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
            Server(
                protocol=Protocol.GRAPH,
                url="https://graph.example.test/v1.0",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
            Server(
                protocol=Protocol.ACTIONS,
                url="https://mail.example.test/actions",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
            Server(
                protocol=Protocol.MANAGESIEVE,
                host="sieve.example.test",
                port=4190,
                tls=TLSMode.STARTTLS,
                authentication=(AuthenticationMethod.PASSWORD_CLEARTEXT,),
            ),
            Server(
                protocol=Protocol.CALDAV,
                url="https://calendar.example.test/dav",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
            Server(
                protocol=Protocol.CARDDAV,
                url="https://contacts.example.test/dav",
                authentication=(AuthenticationMethod.HTTP_BASIC,),
            ),
            Server(
                protocol=Protocol.WEBDAV,
                url="https://files.example.test/dav",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
        ),
        oauth=OAuthConfiguration(
            issuer="https://identity.example.test",
            authorization_url="https://identity.example.test/authorize",
            token_url="https://identity.example.test/token",
            scopes=("openid", "offline_access", "urn:ietf:params:oauth:scope:mail"),
        ),
        help_url="https://support.example.test/mail",
    )


def test_autoconfig_12_golden_contract() -> None:
    body = render_autoconfig(rich_profile())
    root = etree.fromstring(body)

    assert body.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    assert root.tag == "clientConfig"
    assert root.get("version") == "1.2"
    provider = root.find("emailProvider")
    assert provider is not None
    assert provider.get("id") == "example.test"
    assert provider.findtext("domain") == "example.test"

    incoming = provider.findall("incomingServer")
    assert [item.get("type") for item in incoming] == [
        "imap",
        "pop3",
        "jmap",
        "activeSync",
        "graph",
    ]
    assert incoming[0].findtext("socketType") == "SSL"
    assert [item.text for item in incoming[0].findall("authentication")] == [
        "OAuth2",
        "password-cleartext",
    ]
    assert incoming[0].findtext("username") == "%EMAILADDRESS%"
    outgoing = provider.findall("outgoingServer")
    assert len(outgoing) == 1
    assert outgoing[0].findtext("socketType") == "STARTTLS"
    assert [item.text for item in outgoing[0].findall("authentication")] == [
        "OAuth2",
        "SMTP-after-POP",
        "client-IP-address",
    ]

    assert root.find("calendar").get("type") == "caldav"  # type: ignore[union-attr]
    assert root.find("addressbook").get("type") == "carddav"  # type: ignore[union-attr]
    assert root.find("fileShare").get("type") == "webdav"  # type: ignore[union-attr]
    assert root.find("setupServer").get("type") == "managesieve"  # type: ignore[union-attr]
    assert provider.find("incomingServer[@type='actions']") is None
    addressbook_auth = root.find("addressbook/authentication")
    assert addressbook_auth is not None
    assert addressbook_auth.text == "Basic"
    assert addressbook_auth.get("system") == "http"

    oauth = root.find("oAuth2")
    assert oauth is not None
    assert oauth.findtext("issuer") == "https://identity.example.test"
    assert oauth.find("clientID") is None
    assert oauth.find("clientSecret") is None
    assert root.find("registration_endpoint") is None


def test_oauth_use_requires_metadata_and_scopes() -> None:
    profile = AccountProfile(
        provider="example.test",
        domains=("example.test",),
        email_address="user@example.test",
        servers=(
            Server(
                protocol=Protocol.IMAP,
                host="imap.example.test",
                port=993,
                tls=TLSMode.SSL,
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
        ),
    )
    with pytest.raises(AutoconfigRenderError, match="OAuth"):
        render_autoconfig(profile)

    missing_scopes = profile.model_copy(
        update={"oauth": OAuthConfiguration(issuer="https://identity.example.test")}
    )
    with pytest.raises(AutoconfigRenderError, match="scope"):
        render_autoconfig(missing_scopes)


def test_both_autoconfig_routes_return_identical_bytes_and_optional_address(
    tmp_path: Path,
) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
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
imap_auth = plaintext
""",
        encoding="utf-8",
    )
    client = TestClient(create_app(config_path=config))

    traditional = client.get(
        "/mail/config-v1.1.xml", params={"emailaddress": "user@example.test"}
    )
    well_known = client.get("/.well-known/autoconfig/mail/config-v1.1.xml")

    assert traditional.status_code == 200
    assert traditional.headers["content-type"] == "text/xml; charset=utf-8"
    assert traditional.content == well_known.content
    assert traditional.headers["content-length"] == str(len(traditional.content))
    assert b"user@example.test" not in traditional.content


def test_wildcard_domain_requires_address_when_no_synthetic_domain_exists(tmp_path: Path) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        """
[automx]
provider = example.test
domains = *
[global]
backend = static
""",
        encoding="utf-8",
    )
    response = TestClient(create_app(config_path=config)).get("/mail/config-v1.1.xml")
    assert response.status_code == 400


def test_addressless_autoconfig_selects_the_request_host_domain(tmp_path: Path) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        """
[automx]
provider = multi.test
domains = first.test second.test
[global]
backend = static
imap = yes
imap_server = imap.first.test
imap_port = 993
imap_encryption = ssl
imap_auth = plaintext
[second.test]
backend = static
imap = yes
imap_server = imap.second.test
imap_port = 993
imap_encryption = ssl
imap_auth = plaintext
""",
        encoding="utf-8",
    )
    response = TestClient(create_app(config_path=config)).get(
        "/.well-known/autoconfig/mail/config-v1.1.xml",
        headers={"host": "second.test"},
    )

    assert response.status_code == 200
    root = etree.fromstring(response.content)
    assert root.findtext("emailProvider/domain") == "second.test"
    assert root.findtext("emailProvider/incomingServer/hostname") == "imap.second.test"
