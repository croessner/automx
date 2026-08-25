"""Remote protocol probes replacing the legacy automx-test shell script."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import plistlib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, cast

from lxml import etree

from automx.commands.pacc import pacc_bytes


@dataclass(frozen=True, slots=True)
class ProbeResult:
    name: str
    status: str
    detail: str


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(  # type: ignore[no-untyped-def]
        self, request, file_pointer, code, message, headers, new_url
    ) -> None:
        return None


class ProbeClient:
    """Small bounded HTTP client with no implicit redirects or credential output."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float,
        allow_insecure_http: bool,
        basic_auth_environment: str | None,
    ) -> None:
        parts = urllib.parse.urlsplit(base_url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("--base-url must be an absolute HTTP(S) URL")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("--base-url must not contain credentials, query, or fragment")
        if parts.scheme == "http" and not allow_insecure_http:
            raise ValueError("plain HTTP requires --allow-insecure-http")
        if timeout <= 0 or timeout > 60:
            raise ValueError("--timeout must be between 0 and 60 seconds")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._authorization: str | None = None
        if basic_auth_environment is not None:
            credentials = os.environ.get(basic_auth_environment)
            if credentials is None:
                raise ValueError(f"environment variable {basic_auth_environment!r} is not set")
            username, separator, password = credentials.partition(":")
            if not separator or not username or not password:
                raise ValueError("basic-auth environment value must use username:password")
            token = base64.b64encode(credentials.encode()).decode("ascii")
            self._authorization = f"Basic {token}"
        tls_context = ssl.create_default_context()
        tls_context.minimum_version = ssl.TLSVersion.TLSv1_3
        self._opener = urllib.request.build_opener(
            _NoRedirect(), urllib.request.HTTPSHandler(context=tls_context)
        )

    def request(
        self,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
        expected_status: int = 200,
    ) -> bytes:
        headers = {"Accept": "application/json, application/xml, text/xml, */*"}
        if content_type is not None:
            headers["Content-Type"] = content_type
        if self._authorization is not None:
            headers["Authorization"] = self._authorization
        request = urllib.request.Request(  # noqa: S310 - operator-provided, validated origin
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method="POST" if body is not None else "GET",
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                status = response.status
                result = cast(bytes, response.read(1_048_577))
        except urllib.error.HTTPError as exc:
            status = exc.code
            result = exc.read(1_048_577)
        if len(result) > 1_048_576:
            raise ValueError(f"response from {path} exceeds 1 MiB")
        if status != expected_status:
            raise ValueError(f"{path} returned HTTP {status}, expected {expected_status}")
        return result


def _xml(body: bytes) -> etree._Element:
    upper = body.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("response contains a DTD or entity declaration")
    try:
        return etree.fromstring(
            body,
            parser=etree.XMLParser(
                resolve_entities=False,
                no_network=True,
                load_dtd=False,
                huge_tree=False,
            ),
        )
    except etree.XMLSyntaxError as exc:
        raise ValueError("response is not safe, well-formed XML") from exc


def _outlook_request(email_address: str, *, mobile: bool = False) -> bytes:
    kind = "mobilesync" if mobile else "outlook"
    response = "mobilesync/responseschema/2006" if mobile else "outlook/responseschema/2006a"
    root = etree.Element(
        "Autodiscover",
        xmlns=f"http://schemas.microsoft.com/exchange/autodiscover/{kind}/requestschema/2006",
    )
    request = etree.SubElement(root, "Request")
    etree.SubElement(request, "EMailAddress").text = email_address
    etree.SubElement(request, "AcceptableResponseSchema").text = (
        f"http://schemas.microsoft.com/exchange/autodiscover/{response}"
    )
    return cast(bytes, etree.tostring(root, encoding="UTF-8", xml_declaration=True))


def probe_health(client: ProbeClient, _email: str, _experimental: bool) -> list[ProbeResult]:
    document: Any = json.loads(client.request("/health/ready"))
    if document != {"status": "ready"}:
        raise ValueError("readiness response differs from the contract")
    return [ProbeResult("health", "passed", "service is ready")]


def probe_autoconfig(client: ProbeClient, email: str, _experimental: bool) -> list[ProbeResult]:
    query = urllib.parse.urlencode({"emailaddress": email})
    traditional = client.request(f"/mail/config-v1.1.xml?{query}")
    well_known = client.request(f"/.well-known/autoconfig/mail/config-v1.1.xml?{query}")
    if traditional != well_known or _xml(traditional).attrib.get("version") != "1.2":
        raise ValueError("Autoconfig routes or version differ from the contract")
    return [ProbeResult("autoconfig", "passed", "both Autoconfig 1.2 paths agree")]


def probe_autodiscover(
    client: ProbeClient, email: str, experimental: bool
) -> list[ProbeResult]:
    mobile_sync_configured = True
    for mobile in (False, True):
        root = _xml(
            client.request(
                "/autodiscover/autodiscover.xml",
                body=_outlook_request(email, mobile=mobile),
                content_type="application/xml",
            )
        )
        expected = "MobileSync" if mobile else "IMAP"
        types = {value for value in root.itertext() if value}
        if expected not in types:
            if (
                mobile
                and root.findtext(".//{*}ErrorCode") == "602"
                and root.findtext(".//{*}Message") == "Configuration Error"
            ):
                mobile_sync_configured = False
                continue
            raise ValueError(f"Autodiscover response does not contain {expected}")

    unsafe = _xml(
        client.request(
            "/autodiscover/autodiscover.xml",
            body=b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>',
            content_type="application/xml",
        )
    )
    if unsafe.findtext(".//{*}ErrorCode") != "600" or b"root:" in etree.tostring(unsafe):
        raise ValueError("Autodiscover XXE rejection contract failed")

    form = urllib.parse.urlencode(
        {"_mobileconfig": "true", "cn": "automx Probe", "emailaddress": email}
    ).encode("ascii")
    mobileconfig: Any = plistlib.loads(
        client.request(
            "/mobileconfig",
            body=form,
            content_type="application/x-www-form-urlencoded",
        )
    )
    mail_payload = mobileconfig["PayloadContent"][0]
    if "IncomingPassword" in mail_payload or "OutgoingPassword" in mail_payload:
        raise ValueError("mobileconfig response embeds a password")

    results = [
        ProbeResult(
            "autodiscover",
            "passed",
            (
                "Outlook contract passed; MobileSync is not configured"
                if not mobile_sync_configured
                else "Outlook and MobileSync contracts passed"
            ),
        ),
        ProbeResult("mobileconfig", "passed", "Apple profile is password-free"),
    ]
    if experimental:
        query = urllib.parse.urlencode({"Email": email, "Protocol": "EWS"})
        response: Any = json.loads(
            client.request(f"/autodiscover/autodiscover.json?{query}")
        )
        if response.get("Protocol") != "EWS" or not response.get("Url"):
            raise ValueError("Autodiscover v2 EWS response differs from the contract")
        invalid_query = urllib.parse.urlencode({"Email": email, "Protocol": "IMAP"})
        client.request(
            f"/autodiscover/autodiscover.json?{invalid_query}", expected_status=400
        )
        results.append(ProbeResult("autodiscover-v2", "passed", "experimental EWS probe passed"))
    return results


def probe_pacc(client: ProbeClient, _email: str, _experimental: bool) -> list[ProbeResult]:
    body = client.request("/.well-known/user-agent-configuration.json")
    document: Any = json.loads(body)
    if not isinstance(document.get("protocols"), dict):
        raise ValueError("PACC response has no protocols object")
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")
    return [ProbeResult("pacc", "passed", f"UAAC1 digest v=UAAC1; a=sha256; d={digest}")]


_PROBES = {
    "health": probe_health,
    "autoconfig": probe_autoconfig,
    "autodiscover": probe_autodiscover,
    "pacc": probe_pacc,
}


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True, help="automx service origin")
    parser.add_argument("--email", required=True, help="synthetic account to probe")
    parser.add_argument("--timeout", type=float, default=10, help="per-request timeout")
    parser.add_argument(
        "--allow-insecure-http",
        action="store_true",
        help="allow plain HTTP for local or isolated test stacks",
    )
    parser.add_argument(
        "--basic-auth-env",
        help="environment variable containing username:password; never pass a secret in argv",
    )
    parser.add_argument("--include-experimental", action="store_true")
    parser.add_argument(
        "--config",
        help="local automx.conf whose PACC bytes must match the remote response",
    )
    parser.add_argument("--domain", help="domain used with --config")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.set_defaults(handler=run)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("probe", help="test a deployed automx service")
    commands = parser.add_subparsers(dest="probe_command", required=True)
    for name in (*_PROBES, "all"):
        command = commands.add_parser(name, help=f"run {name} protocol probes")
        _add_arguments(command)


def run(args: argparse.Namespace) -> int:
    client = ProbeClient(
        args.base_url,
        timeout=args.timeout,
        allow_insecure_http=args.allow_insecure_http,
        basic_auth_environment=args.basic_auth_env,
    )
    names = tuple(_PROBES) if args.probe_command == "all" else (args.probe_command,)
    results: list[ProbeResult] = []
    for name in names:
        results.extend(_PROBES[name](client, args.email, args.include_experimental))
    if args.config is not None and "pacc" in names:
        _domain, expected = pacc_bytes(args.config, args.domain)
        actual = client.request("/.well-known/user-agent-configuration.json")
        if actual != expected:
            raise ValueError("remote PACC bytes differ from the local configuration")
        results.append(ProbeResult("pacc-parity", "passed", "local and remote bytes agree"))
    if args.format == "json":
        print(json.dumps({"status": "passed", "results": [asdict(item) for item in results]}))
    else:
        for result in results:
            print(f"PASS {result.name}: {result.detail}")
    return 0
