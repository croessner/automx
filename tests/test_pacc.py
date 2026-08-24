from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from automx.app import create_app
from automx.commands.dns import deployment_records
from automx.domain import (
    AccountProfile,
    AuthenticationMethod,
    OAuthConfiguration,
    Protocol,
    Server,
    TLSMode,
)
from automx.renderers.pacc import PaccRenderError, pacc_digest_record, render_pacc

PACC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "protocols": {
            "type": "object",
            "properties": {
                "caldav": {"$ref": "#/$defs/http-server"},
                "carddav": {"$ref": "#/$defs/http-server"},
                "imap": {"$ref": "#/$defs/text-server"},
                "jmap": {"$ref": "#/$defs/http-server"},
                "managesieve": {"$ref": "#/$defs/text-server"},
                "pop3": {"$ref": "#/$defs/text-server"},
                "smtp": {"$ref": "#/$defs/text-server"},
                "webdav": {"$ref": "#/$defs/http-server"},
            },
        },
        "authentication": {
            "type": "object",
            "properties": {
                "oauth-public": {
                    "type": "object",
                    "properties": {"issuer": {"type": "string", "format": "uri"}},
                    "required": ["issuer"],
                },
                "password": {"type": "boolean"},
            },
            "required": ["password"],
        },
        "info": {
            "type": "object",
            "properties": {
                "provider": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "shortName": {"type": "string", "minLength": 1},
                    },
                    "required": ["name"],
                },
                "help": {
                    "type": "object",
                    "properties": {"documentation": {"type": "string", "format": "uri"}},
                },
            },
            "required": ["provider"],
        },
    },
    "required": ["protocols", "info"],
    "$defs": {
        "http-server": {
            "type": "object",
            "properties": {"url": {"type": "string", "format": "uri"}},
            "required": ["url"],
        },
        "text-server": {
            "type": "object",
            "properties": {"host": {"type": "string", "format": "hostname"}},
            "required": ["host"],
        },
    },
}


def pacc_profile() -> AccountProfile:
    return AccountProfile(
        provider="example.test",
        domains=("example.test",),
        email_address="pacc@example.test",
        display_name="Example Provider",
        display_name_short="Example",
        servers=(
            Server(
                protocol=Protocol.IMAP,
                host="imap.example.test",
                port=993,
                tls=TLSMode.SSL,
                authentication=(AuthenticationMethod.OAUTH2,),
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
                port=465,
                tls=TLSMode.SSL,
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
            Server(
                protocol=Protocol.JMAP,
                url="https://jmap.example.test/session",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
            Server(
                protocol=Protocol.CALDAV,
                url="https://sync.example.test/calendar/",
                authentication=(AuthenticationMethod.OAUTH2,),
            ),
        ),
        oauth=OAuthConfiguration(issuer="https://identity.example.test/"),
        help_url="https://support.example.test/mail",
    )


def test_pacc_02_output_validates_against_draft_2020_12_schema() -> None:
    body = render_pacc(pacc_profile())
    document = json.loads(body)
    Draft202012Validator(PACC_SCHEMA).validate(document)

    assert document == {
        "authentication": {
            "oauth-public": {"issuer": "https://identity.example.test/"},
            "password": True,
        },
        "info": {
            "help": {"documentation": "https://support.example.test/mail"},
            "provider": {"name": "Example Provider", "shortName": "Example"},
        },
        "protocols": {
            "caldav": {"url": "https://sync.example.test/calendar/"},
            "imap": {"host": "imap.example.test"},
            "jmap": {"url": "https://jmap.example.test/session"},
            "pop3": {"host": "pop.example.test"},
            "smtp": {"host": "smtp.example.test"},
        },
    }


def test_pacc_bytes_and_uaac1_digest_are_deterministic() -> None:
    body = render_pacc(pacc_profile())
    assert body == render_pacc(pacc_profile())
    expected_digest = base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")
    assert pacc_digest_record(body) == f"v=UAAC1; a=sha256; d={expected_digest}"
    assert pacc_digest_record(body) == (
        "v=UAAC1; a=sha256; d=MOA19C2fw1LnfpriQEArPk+FRkxoE7UVaunADBmu7G8="
    )


def test_pacc_route_serves_exact_digest_input_bytes(tmp_path: Path) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        """
[automx]
provider = example.test
domains = example.test
[DEFAULT]
account_name = Example Provider
account_name_short = Example
[global]
backend = static
imap = yes
imap_server = imap.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = plaintext
smtp = yes
smtp_server = smtp.example.test
smtp_port = 465
smtp_encryption = ssl
smtp_auth = plaintext
oauth_issuer = https://identity.example.test/
""",
        encoding="utf-8",
    )
    app = create_app(config_path=config)
    response = TestClient(app).get("/.well-known/user-agent-configuration.json")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content == render_pacc(app.state.repository.resolve("pacc@example.test"))
    assert response.headers["content-length"] == str(len(response.content))


def test_pacc_route_selects_host_domain_and_matches_its_dns_digest(tmp_path: Path) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        """
[automx]
provider = multi.test
domains = first.test second.test
[global]
backend = static
account_name = First Provider
imap = yes
imap_server = imap.first.test
imap_port = 993
imap_encryption = ssl
imap_auth = plaintext
[second.test]
backend = static
account_name = Second Provider
imap = yes
imap_server = imap.second.test
imap_port = 993
imap_encryption = ssl
imap_auth = plaintext
""",
        encoding="utf-8",
    )
    app = create_app(config_path=config)
    client = TestClient(app)

    response = client.get(
        "/.well-known/user-agent-configuration.json",
        headers={"host": "ua-auto-config.second.test"},
    )
    expected = render_pacc(app.state.repository.resolve("pacc@second.test"))
    assert response.status_code == 200
    assert response.content == expected

    _domain, records = deployment_records(
        config_path=str(config),
        domain="second.test",
        service_host="config.example.test",
    )
    digest = next(record.value for record in records if record.type == "TXT")
    assert digest == pacc_digest_record(response.content)

    unknown = client.get(
        "/.well-known/user-agent-configuration.json",
        headers={"host": "ua-auto-config.unknown.test"},
    )
    assert unknown.status_code == 404


def test_pacc_rejects_missing_provider_info_and_non_draft_endpoints() -> None:
    missing_info = pacc_profile().model_copy(update={"display_name": None})
    with pytest.raises(PaccRenderError, match="provider name"):
        render_pacc(missing_info)

    wrong_port = pacc_profile().model_copy(
        update={
            "servers": (
                Server(
                    protocol=Protocol.IMAP,
                    host="imap.example.test",
                    port=143,
                    tls=TLSMode.STARTTLS,
                    authentication=(AuthenticationMethod.PASSWORD_CLEARTEXT,),
                ),
            )
        }
    )
    with pytest.raises(PaccRenderError, match="default TLS port"):
        render_pacc(wrong_port)

    explicit_https_port = pacc_profile().model_copy(
        update={
            "servers": (
                Server(
                    protocol=Protocol.JMAP,
                    url="https://jmap.example.test:443/session",
                ),
            )
        }
    )
    with pytest.raises(PaccRenderError, match="explicit port"):
        render_pacc(explicit_https_port)
