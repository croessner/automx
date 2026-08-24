from __future__ import annotations

import plistlib
from pathlib import Path

from fastapi.testclient import TestClient

from automx.app import create_app


def config(tmp_path: Path) -> Path:
    path = tmp_path / "automx.conf"
    path.write_text(
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = static
account_name = Example Mail
imap = yes
imap_server = imap.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = oauth2, plaintext
smtp = yes
smtp_server = smtp.example.test
smtp_port = 465
smtp_encryption = ssl
smtp_auth = plaintext
""",
        encoding="utf-8",
    )
    return path


def test_mobileconfig_is_deterministic_and_contains_no_password(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=config(tmp_path)))
    form = {"_mobileconfig": "true", "cn": "Example User", "emailaddress": "user@example.test"}

    first = client.post("/mobileconfig", data=form)
    second = client.post("/mobileconfig", data=form)

    assert first.status_code == 200
    assert first.content == second.content
    assert first.headers["content-type"].startswith("application/x-apple-aspen-config")
    assert first.headers["content-disposition"] == 'attachment; filename="automx.mobileconfig"'
    profile = plistlib.loads(first.content)
    mail = profile["PayloadContent"][0]
    assert mail["EmailAccountName"] == "Example User"
    assert mail["IncomingMailServerAuthentication"] == "EmailAuthPassword"
    assert mail["IncomingMailServerHostName"] == "imap.example.test"
    assert mail["IncomingMailServerUsername"] == "user@example.test"
    assert mail["OutgoingMailServerHostName"] == "smtp.example.test"
    assert mail["OutgoingMailServerUsername"] == "user@example.test"
    assert "IncomingPassword" not in mail
    assert "OutgoingPassword" not in mail


def test_mobileconfig_browser_form_is_password_free_and_root_redirects(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=config(tmp_path)))

    root = client.get("/")
    form = client.get("/mobileconfig")

    assert root.status_code == 200
    assert root.url.path == "/mobileconfig"
    assert root.history[0].status_code == 307
    assert form.status_code == 200
    assert form.headers["content-type"].startswith("text/html")
    assert form.headers["cache-control"] == "no-store"
    assert "form-action 'self'" in form.headers["content-security-policy"]
    assert form.headers["referrer-policy"] == "no-referrer"
    assert form.headers["x-content-type-options"] == "nosniff"
    assert 'action="/mobileconfig"' in form.text
    assert 'name="emailaddress"' in form.text
    assert 'name="cn"' in form.text
    assert "password" not in form.text.lower()


def test_mobileconfig_rejects_passwords_and_ambiguous_forms(tmp_path: Path) -> None:
    client = TestClient(create_app(config_path=config(tmp_path)))

    password = client.post(
        "/mobileconfig",
        data={"emailaddress": "user@example.test", "password": "do-not-store-this"},
    )
    assert password.status_code == 400
    assert password.json()["error"] == "password_not_accepted"
    assert "do-not-store-this" not in password.text

    duplicate = client.post(
        "/mobileconfig",
        content="emailaddress=user%40example.test&emailaddress=other%40example.test",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["error"] == "invalid_form"
