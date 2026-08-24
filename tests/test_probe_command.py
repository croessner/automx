from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest
from fastapi.testclient import TestClient

from automx.app import create_app
from automx.cli import main
from automx.commands import probe
from automx.renderers.autodiscover import (
    MOBILE_REQUEST_NAMESPACE,
    MOBILE_RESPONSE_NAMESPACE,
    render_autodiscover_error,
)

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "contrib/e2e/automx.conf"


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def read(self, _limit: int) -> bytes:
        return self.body


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.last_request: Request | None = None
        self.last_timeout: float | None = None

    def open(self, request: Request, *, timeout: float) -> FakeResponse:
        self.last_request = request
        self.last_timeout = timeout
        return self.response


class LocalProbeClient:
    def __init__(self, config: Path = CONFIG) -> None:
        self.client = TestClient(create_app(config_path=config))

    def request(
        self,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        expected_status: int = 200,
    ) -> bytes:
        headers = {"content-type": content_type} if content_type else {}
        response = (
            self.client.post(path, content=body, headers=headers)
            if body is not None
            else self.client.get(path, headers=headers)
        )
        assert response.status_code == expected_status
        return response.content


class InvalidMobileSyncProbeClient(LocalProbeClient):
    def request(
        self,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        expected_status: int = 200,
    ) -> bytes:
        if body is not None and MOBILE_REQUEST_NAMESPACE.encode("ascii") in body:
            return render_autodiscover_error(
                601,
                "Provider Not Available",
                response_namespace=MOBILE_RESPONSE_NAMESPACE,
            )
        return super().request(
            path,
            body=body,
            content_type=content_type,
            expected_status=expected_status,
        )


def test_every_remote_probe_contract_against_the_real_asgi_app() -> None:
    client: Any = LocalProbeClient()

    assert probe.probe_health(client, "user@example.test", False)[0].status == "passed"
    assert probe.probe_autoconfig(client, "user@example.test", False)[0].status == "passed"
    autodiscover = probe.probe_autodiscover(client, "user@example.test", True)
    assert [result.name for result in autodiscover] == [
        "autodiscover",
        "mobileconfig",
        "autodiscover-v2",
    ]
    assert "v=UAAC1" in probe.probe_pacc(client, "user@example.test", False)[0].detail


def test_autodiscover_probe_accepts_the_schema_error_when_mobile_sync_is_absent() -> None:
    client: Any = LocalProbeClient(ROOT / "contrib/node1/automx.conf")

    results = probe.probe_autodiscover(client, "probe@roessner-net.de", False)

    assert results[0].status == "passed"
    assert "not configured" in results[0].detail


def test_autodiscover_probe_rejects_a_different_mobile_sync_error() -> None:
    client: Any = InvalidMobileSyncProbeClient(ROOT / "contrib/node1/automx.conf")

    with pytest.raises(ValueError, match="does not contain MobileSync"):
        probe.probe_autodiscover(client, "probe@roessner-net.de", False)


def test_probe_all_cli_reports_json_and_local_pacc_parity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    local = LocalProbeClient()
    monkeypatch.setattr(probe, "ProbeClient", lambda *args, **kwargs: local)

    result = main(
        [
            "probe",
            "all",
            "--base-url",
            "https://automx.example.test",
            "--email",
            "user@example.test",
            "--include-experimental",
            "--config",
            str(CONFIG),
            "--domain",
            "example.test",
            "--format",
            "json",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert '"status": "passed"' in output
    assert '"name": "pacc-parity"' in output
    assert "synthetic-secret" not in output


def test_probe_all_detects_remote_local_pacc_mismatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    local = LocalProbeClient()
    original = local.request

    def mismatching(path: str, **kwargs: Any) -> bytes:
        body = original(path, **kwargs)
        if path == "/.well-known/user-agent-configuration.json":
            return body + b" "
        return body

    local.request = mismatching  # type: ignore[method-assign]
    monkeypatch.setattr(probe, "ProbeClient", lambda *args, **kwargs: local)

    result = main(
        [
            "probe",
            "pacc",
            "--base-url",
            "https://automx.example.test",
            "--email",
            "user@example.test",
            "--config",
            str(CONFIG),
        ]
    )

    assert result == 2
    assert "remote PACC bytes differ" in capsys.readouterr().err


def test_probe_http_client_validates_origin_auth_and_response_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = FakeOpener(FakeResponse(b"ok"))
    monkeypatch.setattr(probe.urllib.request, "build_opener", lambda *_handlers: opener)
    monkeypatch.setenv("AUTOMX_TEST_BASIC", "operator:synthetic-credential")
    client = probe.ProbeClient(
        "https://automx.example.test/",
        timeout=2,
        allow_insecure_http=False,
        basic_auth_environment="AUTOMX_TEST_BASIC",
    )

    assert client.request("/health", body=b"x", content_type="text/plain") == b"ok"
    assert opener.last_request is not None
    assert opener.last_request.full_url == "https://automx.example.test/health"
    assert opener.last_request.method == "POST"
    assert opener.last_request.get_header("Authorization", "").startswith("Basic ")
    assert opener.last_request.get_header("Content-type") == "text/plain"
    assert opener.last_timeout == 2

    opener.response = FakeResponse(b"wrong", status=201)
    with pytest.raises(ValueError, match="expected 200"):
        client.request("/status")
    opener.response = FakeResponse(b"x" * 1_048_577)
    with pytest.raises(ValueError, match="exceeds 1 MiB"):
        client.request("/large")


@pytest.mark.parametrize(
    ("base_url", "timeout", "environment", "message"),
    [
        ("ftp://automx.example.test", 1, None, "absolute HTTP"),
        ("https://user@automx.example.test", 1, None, "must not contain credentials"),
        ("https://automx.example.test", 0, None, "timeout"),
        ("https://automx.example.test", 1, "MISSING_AUTOMX_AUTH", "is not set"),
    ],
)
def test_probe_http_client_rejects_unsafe_options(
    base_url: str,
    timeout: float,
    environment: str | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        probe.ProbeClient(
            base_url,
            timeout=timeout,
            allow_insecure_http=False,
            basic_auth_environment=environment,
        )


def test_probe_safe_xml_and_redirect_contracts() -> None:
    assert probe._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other") is None
    with pytest.raises(ValueError, match="DTD"):
        probe._xml(b"<!DOCTYPE x><x/>")
    with pytest.raises(ValueError, match="well-formed XML"):
        probe._xml(b"<broken>")
