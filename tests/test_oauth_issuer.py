"""Issuer publication contracts for OAuth public clients draft -06."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from lxml import etree
from pydantic import ValidationError

from automx.app import create_app
from automx.domain import OAuthConfiguration


@pytest.mark.parametrize(
    "suffix",
    [
        "/.",
        "/..",
        "/a/./b",
        "/a/../b",
        "/a/.. /b",
        "/%2e",
        "/%2E%2e",
        "/%61cme",
        "/%41",
        "/%30",
        "/%2d",
        "/%5F",
        "/%7e",
        "/bad%",
        "/bad%2",
        "/bad%GG",
        "/a b",
        "/a\\b",
        "/a\tb",
        "/a\nb",
        "/a\rb",
        "/a\x00b",
        "/issuer?",
        "/issuer#",
        "/café",
    ],
)
def test_issuer_rejects_noncanonical_or_invalid_uri_paths(suffix: str) -> None:
    with pytest.raises(ValidationError):
        OAuthConfiguration(issuer=f"https://identity.example.test{suffix}")


@pytest.mark.parametrize("whitespace", [" ", "\t", "\n"])
def test_issuer_is_not_silently_trimmed(whitespace: str) -> None:
    with pytest.raises(ValidationError):
        OAuthConfiguration(issuer=f"{whitespace}https://identity.example.test/")


@pytest.mark.parametrize("value", [b"https://identity.example.test/a/../b", 123, None])
def test_issuer_requires_a_string(value: object) -> None:
    with pytest.raises(ValidationError):
        OAuthConfiguration.model_validate({"issuer": value})


@pytest.mark.parametrize(
    "issuer",
    [
        "https://identity.example.test",
        "https://identity.example.test/",
        "https://identity.example.test/acme/",
        "https://identity.example.test/a.../b",
        "https://identity.example.test/a.b/~tenant_1-2",
        "https://identity.example.test/a%2Fb/%3f/%23/%25/%C3%A9",
        "https://identity.example.test:8443/tenant",
        "https://[2001:db8::1]/tenant/",
    ],
)
def test_valid_issuer_is_preserved_exactly(issuer: str) -> None:
    assert OAuthConfiguration(issuer=issuer).issuer == issuer


def issuer_config(tmp_path: Path, issuer: str) -> Path:
    """Exercise the real INI -> domain -> HTTP publication boundary."""
    path = tmp_path / "automx.conf"
    path.write_text(
        f"""[automx]
provider = example.test
domains = example.test
[global]
backend = static
account_name = Example Provider
imap = yes
imap_server = mail.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = oauth2
oauth_issuer = {issuer}
oauth_scope = urn:ietf:params:oauth:scope:mail
""",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("path", ["/a/../b", "/%61cme"])
def test_invalid_issuer_cannot_be_published(tmp_path: Path, path: str) -> None:
    client = TestClient(
        create_app(config_path=issuer_config(tmp_path, f"https://identity.example.test{path}"))
    )
    for endpoint in ("/mail/config-v1.1.xml", "/.well-known/user-agent-configuration.json"):
        response = client.get(endpoint, params={"emailaddress": "user@example.test"})
        assert response.status_code == 400
        assert response.json() == {
            "error": "invalid_request",
            "message": "account configuration unavailable",
        }


def test_path_issuer_with_trailing_slash_survives_both_formats(tmp_path: Path) -> None:
    issuer = "https://identity.example.test/tenant/"
    client = TestClient(create_app(config_path=issuer_config(tmp_path, issuer)))
    xml = client.get("/mail/config-v1.1.xml", params={"emailaddress": "user@example.test"})
    assert xml.status_code == 200
    assert etree.fromstring(xml.content).findtext("oAuth2/issuer") == issuer
    pacc = client.get("/.well-known/user-agent-configuration.json")
    assert pacc.status_code == 200
    assert pacc.json()["authentication"]["oauth-public"] == {"issuer": issuer}
