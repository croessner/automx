"""Cross-format contracts for DAV endpoints and OAuth-only deployments."""

from __future__ import annotations

import base64
import hashlib
import plistlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lxml import etree

from automx.app import create_app
from automx.domain import Protocol, Server
from automx.renderers.pacc import pacc_digest_record


def dav_config(tmp_path: Path, *, dav_auth: str = "oauth2", mail_auth: str = "oauth2") -> Path:
    """Configure both DAV services and mail with explicitly selected authentication."""
    path = tmp_path / "automx.conf"
    path.write_text(
        f"""
[automx]
provider = example.test
domains = example.test
[global]
backend = static
account_name = Example Provider
imap = yes
imap_server = mail.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = {mail_auth}
smtp = yes
smtp_server = mail.example.test
smtp_port = 465
smtp_encryption = ssl
smtp_auth = {mail_auth}
caldav = yes
caldav_url = https://dav.example.test/calendars/
caldav_auth = {dav_auth}
carddav = yes
carddav_url = https://dav.example.test/contacts/
carddav_auth = {dav_auth}
oauth_issuer = https://identity.example.test
oauth_scope = openid offline_access mail calendar contacts
""",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("service", ["caldav", "carddav"])
@pytest.mark.parametrize("port", ["0", "65536", "bad", "-1"])
def test_invalid_dav_port_is_a_controlled_configuration_error(
    tmp_path: Path, service: str, port: str
) -> None:
    path = dav_config(tmp_path, dav_auth="http-basic", mail_auth="plaintext")
    path.write_text(
        path.read_text().replace(
            f"{service}_url = https://dav.example.test/",
            f"{service}_url = https://dav.example.test:{port}/",
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(config_path=path))
    response = client.post(
        "/mobileconfig", data={"_mobileconfig": "true", "emailaddress": "user@example.test"}
    )
    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_request",
        "message": "account configuration unavailable",
    }


@pytest.mark.parametrize("authority", ["dav.example.test", "dav.example.test:1", "[2001:db8::1]:65535"])
def test_valid_dav_url_ports_are_preserved(authority: str) -> None:
    url = f"https://{authority}/dav/"
    assert Server(protocol=Protocol.CALDAV, url=url).url == url


def test_oauth_only_dav_is_published_by_autoconfig_and_pacc(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=dav_config(tmp_path)))
    response = client.get(
        "/mail/config-v1.1.xml", params={"emailaddress": "user@example.test"}
    )
    assert response.status_code == 200
    root = etree.fromstring(response.content)
    for element, protocol in (("incomingServer", "imap"), ("outgoingServer", "smtp")):
        node = root.find(f"emailProvider/{element}[@type='{protocol}']")
        assert node is not None
        assert [auth.text for auth in node.findall("authentication")] == ["OAuth2"]
    for element, service, path in (
        ("calendar", "caldav", "calendars"),
        ("addressbook", "carddav", "contacts"),
    ):
        node = root.find(f"{element}[@type='{service}']")
        assert node is not None
        assert node.findtext("url") == f"https://dav.example.test/{path}/"
        assert [auth.text for auth in node.findall("authentication")] == ["OAuth2"]
    assert root.findtext("oAuth2/issuer") == "https://identity.example.test"
    assert root.findtext("oAuth2/scope") == "openid offline_access mail calendar contacts"

    pacc = client.get("/.well-known/user-agent-configuration.json")
    assert pacc.status_code == 200
    assert pacc.json()["authentication"] == {
        "password": False,
        "oauth-public": {"issuer": "https://identity.example.test"},
    }
    assert pacc.json()["protocols"]["caldav"] == {"url": "https://dav.example.test/calendars/"}
    assert pacc.json()["protocols"]["carddav"] == {"url": "https://dav.example.test/contacts/"}
    assert pacc.json()["protocols"]["imap"] == {"host": "mail.example.test"}
    assert pacc.json()["protocols"]["submit"] == {"host": "mail.example.test"}
    digest = base64.b64encode(hashlib.sha256(pacc.content).digest()).decode("ascii")
    assert pacc_digest_record(pacc.content) == f"v=UAAC1; a=sha256; d={digest}"

    mobileconfig = client.post(
        "/mobileconfig", data={"_mobileconfig": "true", "emailaddress": "user@example.test"}
    )
    assert mobileconfig.status_code == 422
    assert mobileconfig.json()["error"] == "unsupported_configuration"


@pytest.mark.parametrize("dav_auth,expected_accounts", [("oauth2", 1), ("oauth2, http-basic", 3)])
def test_mobileconfig_dav_requires_a_supported_authentication_alternative(
    tmp_path: Path, dav_auth: str, expected_accounts: int
) -> None:
    client = TestClient(
        create_app(config_path=dav_config(tmp_path, dav_auth=dav_auth, mail_auth="plaintext"))
    )
    response = client.post(
        "/mobileconfig", data={"_mobileconfig": "true", "emailaddress": "user@example.test"}
    )
    assert response.status_code == 200
    assert len(plistlib.loads(response.content)["PayloadContent"]) == expected_accounts
