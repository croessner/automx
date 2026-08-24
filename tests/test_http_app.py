from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from automx.app import create_app


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "automx.conf"
    path.write_text(
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
    return path


def test_health_endpoints_are_minimal_and_do_not_expose_configuration(config_path: Path) -> None:
    client = TestClient(create_app(config_path=config_path))

    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert "example.test" not in ready.text


def test_protocol_routes_have_framework_method_contracts(config_path: Path) -> None:
    client = TestClient(create_app(config_path=config_path))

    assert client.post("/mail/config-v1.1.xml").status_code == 405
    response = client.get(
        "/mail/config-v1.1.xml", params={"emailaddress": "user@example.test"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/xml; charset=utf-8"


def test_autodiscover_requires_xml_and_rejects_malformed_or_active_content(
    config_path: Path,
) -> None:
    client = TestClient(create_app(config_path=config_path))

    unsupported = client.post(
        "/autodiscover/autodiscover.xml",
        content=b"x=1",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert unsupported.status_code == 415

    malformed = client.post(
        "/autodiscover/autodiscover.xml",
        content=b"<Autodiscover>",
        headers={"content-type": "application/xml"},
    )
    assert malformed.status_code == 200
    assert b"<ErrorCode>600</ErrorCode>" in malformed.content

    doctype = client.post(
        "/autodiscover/autodiscover.xml",
        content=b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///etc/passwd">]><x>&secret;</x>',
        headers={"content-type": "text/xml"},
    )
    assert doctype.status_code == 200
    assert b"<ErrorCode>600</ErrorCode>" in doctype.content
    assert b"root:" not in doctype.content


def test_body_limit_is_enforced_with_and_without_a_content_length(config_path: Path) -> None:
    client = TestClient(create_app(config_path=config_path, max_request_bytes=1_024))
    body = b"<x>" + (b"a" * 2_048) + b"</x>"

    declared = client.post(
        "/autodiscover/autodiscover.xml",
        content=body,
        headers={"content-type": "application/xml"},
    )
    assert declared.status_code == 413

    def chunks() -> Iterator[bytes]:
        yield body

    streamed = client.post(
        "/autodiscover/autodiscover.xml",
        content=chunks(),
        headers={"content-type": "application/xml"},
    )
    assert streamed.status_code == 413


def test_authorization_body_and_query_secrets_are_not_logged(
    config_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="automx.access")
    client = TestClient(create_app(config_path=config_path))

    client.post(
        "/autodiscover/autodiscover.xml?password=query-secret",
        content=b"<broken>body-secret",
        headers={
            "authorization": "Basic header-secret",
            "content-type": "application/xml",
            "cookie": "session=cookie-secret",
        },
    )

    log_output = caplog.text
    assert "POST /autodiscover/autodiscover.xml 200" in log_output
    assert "query-secret" not in log_output
    assert "body-secret" not in log_output
    assert "header-secret" not in log_output
    assert "cookie-secret" not in log_output


def test_path_account_identifier_is_replaced_by_route_template_in_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        """
[automx]
provider = example.test
domains = example.test
autodiscover_v2 = yes
[global]
backend = static
ews = yes
ews_url = https://mail.example.test/EWS/Exchange.asmx
""",
        encoding="utf-8",
    )
    caplog.set_level(logging.INFO, logger="automx.access")
    client = TestClient(create_app(config_path=config))

    response = client.get(
        "/autodiscover/autodiscover.json/v1.0/user@example.test",
        params={"Protocol": "EWS"},
    )

    assert response.status_code == 200
    assert "/autodiscover/autodiscover.json/v1.0/{email_address}" in caplog.text
    assert "user@example.test" not in caplog.text

    redirect = client.get(
        "/autodiscover/autodiscover.json/v1.0/private@example.test/",
        params={"Protocol": "EWS"},
        follow_redirects=False,
    )
    assert redirect.status_code == 307
    assert "private@example.test" not in caplog.text
