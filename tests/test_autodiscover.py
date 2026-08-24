from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from lxml import etree

from automx.app import create_app
from automx.renderers.autodiscover import (
    MOBILE_REQUEST_NAMESPACE,
    MOBILE_RESPONSE_NAMESPACE,
    OUTLOOK_REQUEST_NAMESPACE,
    OUTLOOK_RESPONSE_NAMESPACE,
    RESPONSE_NAMESPACE,
)


def configuration(tmp_path: Path, *, enable_v2: bool = True) -> Path:
    path = tmp_path / "automx.conf"
    path.write_text(
        f"""
[automx]
provider = example.test
domains = example.test
autodiscover_v2 = {"yes" if enable_v2 else "no"}
[DEFAULT]
account_name = Example User
[global]
backend = static
imap = yes
imap_server = imap.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = plaintext
pop = yes
pop_server = pop.example.test
pop_port = 995
pop_encryption = ssl
pop_auth = plaintext
smtp = yes
smtp_server = smtp.example.test
smtp_port = 587
smtp_encryption = starttls
smtp_auth = ntlm
activesync = yes
activesync_url = https://mail.example.test/Microsoft-Server-ActiveSync
ews = yes
ews_url = https://mail.example.test/EWS/Exchange.asmx
actions = yes
actions_url = https://mail.example.test/actions
actions_server_location = EUR
""",
        encoding="utf-8",
    )
    return path


def request_xml(namespace: str, response_schema: str, email: str = "user@example.test") -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="{namespace}">
  <Request>
    <EMailAddress>{email}</EMailAddress>
    <AcceptableResponseSchema>{response_schema}</AcceptableResponseSchema>
  </Request>
</Autodiscover>""".encode()


def test_outlook_response_has_one_protocol_element_per_service(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=configuration(tmp_path)))
    response = client.post(
        "/autodiscover/autodiscover.xml",
        content=request_xml(OUTLOOK_REQUEST_NAMESPACE, OUTLOOK_RESPONSE_NAMESPACE),
        headers={"content-type": "text/xml"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/xml; charset=utf-8"
    root = etree.fromstring(response.content)
    assert root.tag == f"{{{RESPONSE_NAMESPACE}}}Autodiscover"
    protocols = root.findall(f".//{{{OUTLOOK_RESPONSE_NAMESPACE}}}Protocol")
    assert [node.findtext(f"{{{OUTLOOK_RESPONSE_NAMESPACE}}}Type") for node in protocols] == [
        "IMAP",
        "POP3",
        "SMTP",
        "EXPR",
    ]
    assert [node.findtext(f"{{{OUTLOOK_RESPONSE_NAMESPACE}}}Server") for node in protocols[:3]] == [
        "imap.example.test",
        "pop.example.test",
        "smtp.example.test",
    ]
    assert protocols[0].findtext(f"{{{OUTLOOK_RESPONSE_NAMESPACE}}}LoginName") == (
        "user@example.test"
    )
    assert protocols[3].findtext(f"{{{OUTLOOK_RESPONSE_NAMESPACE}}}Server") == (
        "mail.example.test"
    )
    assert protocols[3].findtext(f"{{{OUTLOOK_RESPONSE_NAMESPACE}}}EwsUrl") == (
        "https://mail.example.test/EWS/Exchange.asmx"
    )


def test_mobile_response_uses_only_configured_activesync_url(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=configuration(tmp_path)))
    response = client.post(
        "/autodiscover/autodiscover.xml",
        content=request_xml(MOBILE_REQUEST_NAMESPACE, MOBILE_RESPONSE_NAMESPACE),
        headers={"content-type": "text/xml"},
    )

    root = etree.fromstring(response.content)
    assert root.findtext(f".//{{{MOBILE_RESPONSE_NAMESPACE}}}EMailAddress") == (
        "user@example.test"
    )
    assert root.find(f".//{{{MOBILE_RESPONSE_NAMESPACE}}}EmailAddress") is None
    assert root.findtext(f".//{{{MOBILE_RESPONSE_NAMESPACE}}}Type") == "MobileSync"
    assert root.findtext(f".//{{{MOBILE_RESPONSE_NAMESPACE}}}Url") == (
        "https://mail.example.test/Microsoft-Server-ActiveSync"
    )


def test_namespace_and_schema_errors_are_protocol_xml_not_http_500(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=configuration(tmp_path)))
    wrong_namespace = client.post(
        "/autodiscover/autodiscover.xml",
        content=request_xml("urn:not-autodiscover", OUTLOOK_RESPONSE_NAMESPACE),
        headers={"content-type": "application/xml"},
    )
    assert wrong_namespace.status_code == 200
    assert etree.fromstring(wrong_namespace.content).findtext(".//{*}ErrorCode") == "600"

    unknown_schema = client.post(
        "/autodiscover/autodiscover.xml",
        content=request_xml(MOBILE_REQUEST_NAMESPACE, "https://attacker.example/schema"),
        headers={"content-type": "text/xml"},
    )
    assert unknown_schema.status_code == 200
    assert etree.fromstring(unknown_schema.content).findtext(".//{*}ErrorCode") == "601"
    assert b"attacker.example" not in unknown_schema.content


def test_malformed_xml_uses_error_600_but_oversized_body_stays_http_413(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=configuration(tmp_path), max_request_bytes=1_024))
    malformed = client.post(
        "/autodiscover/autodiscover.xml",
        content=b"<Autodiscover>",
        headers={"content-type": "text/xml"},
    )
    assert malformed.status_code == 200
    assert etree.fromstring(malformed.content).findtext(".//{*}ErrorCode") == "600"

    oversized = client.post(
        "/autodiscover/autodiscover.xml",
        content=b"<x>" + (b"x" * 2_048) + b"</x>",
        headers={"content-type": "text/xml"},
    )
    assert oversized.status_code == 413


def test_autodiscover_v2_is_feature_gated_and_allowlisted(tmp_path: Path) -> None:
    disabled = TestClient(create_app(config_path=configuration(tmp_path, enable_v2=False)))
    assert (
        disabled.get(
            "/autodiscover/autodiscover.json/v1.0/user@example.test",
            params={"Protocol": "Actions"},
        ).status_code
        == 404
    )

    enabled = TestClient(create_app(config_path=configuration(tmp_path, enable_v2=True)))
    response = enabled.get(
        "/autodiscover/autodiscover.json/v1.0/user@example.test",
        params={"Protocol": "Actions"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "Protocol": "Actions",
        "Url": "https://mail.example.test/actions",
        "ServerLocation": "EUR",
    }

    query_route = enabled.get(
        "/autodiscover/autodiscover.json",
        params={"Email": "user@example.test", "Protocol": "EWS"},
    )
    assert query_route.json() == {
        "Protocol": "EWS",
        "Url": "https://mail.example.test/EWS/Exchange.asmx",
    }

    rejected = enabled.get(
        "/autodiscover/autodiscover.json/v1.0/user@example.test",
        params={"Protocol": "IMAP", "url": "https://attacker.example/steal"},
    )
    assert rejected.status_code == 400
    assert "attacker.example" not in rejected.text


def test_v2_does_not_enumerate_mailboxes_and_never_follows_user_urls(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=configuration(tmp_path)))
    first = client.get(
        "/autodiscover/autodiscover.json/v1.0/exists@example.test",
        params={"Protocol": "EWS"},
    )
    second = client.get(
        "/autodiscover/autodiscover.json/v1.0/does-not-exist@example.test",
        params={"Protocol": "EWS"},
    )
    assert first.status_code == second.status_code == 200
    assert first.content == second.content


def test_v2_path_uses_documented_protocol_casing_and_maps_validation_to_400(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(config_path=configuration(tmp_path)))

    supported = client.get(
        "/autodiscover/autodiscover.json/v1.0/user@example.test",
        params={"Protocol": "EWS"},
    )
    assert supported.status_code == 200
    assert supported.json()["Protocol"] == "EWS"
    assert (
        client.get("/autodiscover/autodiscover.json/v1.0/user@example.test").status_code
        == 400
    )
