from __future__ import annotations

import plistlib
from pathlib import Path

from fastapi.testclient import TestClient

from automx.app import create_app


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "automx.conf"
    path.write_text(body, encoding="utf-8")
    return path


def test_file_backend_serves_validated_static_autoconfig(tmp_path: Path) -> None:
    expected = b'<?xml version="1.0"?><clientConfig version="1.2"><emailProvider id="x"/></clientConfig>'
    (tmp_path / "autoconfig.xml").write_bytes(expected)
    config = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = file
autoconfig = autoconfig.xml
""",
    )

    response = TestClient(create_app(config_path=config)).get(
        "/mail/config-v1.1.xml", params={"emailaddress": "user@example.test"}
    )

    assert response.status_code == 200
    assert response.content == expected


def test_file_backend_rejects_active_xml_without_leaking_it(tmp_path: Path) -> None:
    (tmp_path / "autoconfig.xml").write_bytes(
        b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><clientConfig>&e;</clientConfig>'
    )
    config = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = file
autoconfig = autoconfig.xml
""",
    )

    response = TestClient(create_app(config_path=config)).get(
        "/mail/config-v1.1.xml", params={"emailaddress": "user@example.test"}
    )

    assert response.status_code == 500
    assert response.json()["error"] == "invalid_static_document"
    assert "passwd" not in response.text


def test_file_backend_rejects_mobileconfig_password_keys(tmp_path: Path) -> None:
    document = {
        "PayloadType": "Configuration",
        "PayloadContent": [{"IncomingPassword": "synthetic-secret"}],
    }
    (tmp_path / "profile.mobileconfig").write_bytes(plistlib.dumps(document))
    config = write_config(
        tmp_path,
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = file
mobileconfig = profile.mobileconfig
""",
    )

    response = TestClient(create_app(config_path=config)).post(
        "/mobileconfig", data={"emailaddress": "user@example.test"}
    )

    assert response.status_code == 500
    assert response.json()["error"] == "invalid_static_document"
    assert "synthetic-secret" not in response.text
