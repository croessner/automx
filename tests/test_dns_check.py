from __future__ import annotations

import argparse
import json
from pathlib import Path

import dns.name
import pytest

import automx.dns_contracts as dns_contracts
from automx.cli import build_parser, main
from automx.commands.dns import (
    DNSContractChecker,
    DNSLookupError,
    DNSRecord,
    run_check,
)
from automx.dns_contracts import (
    DNSAnswer,
    DnspythonDNSResolver,
    DNSRecordChecker,
    normalize_hostname,
    normalize_rdata,
)

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "contrib/e2e/automx.conf"
SERVICE_HOST = "automx.example.net"


class FakeDNSResolver:
    """Deterministic in-memory resolver for DNS contract tests."""

    def __init__(
        self,
        records: dict[tuple[str, str], tuple[str, ...]],
        *,
        errors: set[tuple[str, str]] | None = None,
        aliases: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self.records = records
        self.errors = errors or set()
        self.aliases = aliases or {}
        self.description = "fake resolver"

    def lookup(self, name: str, record_type: str) -> DNSAnswer:
        key = (name, record_type)
        if key in self.errors:
            raise DNSLookupError("synthetic lookup failure")
        return DNSAnswer(
            values=self.records.get(key, ()),
            canonical_name=self.aliases.get(key, name),
        )


def exact_records(domain: str = "example.test") -> dict[tuple[str, str], tuple[str, ...]]:
    digest = "v=UAAC1; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE="
    target = f"{SERVICE_HOST}."
    return {
        (SERVICE_HOST, "A"): ("192.0.2.10",),
        (f"autoconfig.{domain}", "CNAME"): (target,),
        (f"autodiscover.{domain}", "CNAME"): (target,),
        (f"_autodiscover._tcp.{domain}", "SRV"): (f"0 0 443 {target}",),
        (f"ua-auto-config.{domain}", "CNAME"): (target,),
        (f"_ua-auto-config.{domain}", "TXT"): (digest,),
    }


def check_arguments(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "config": str(CONFIG),
        "domain": None,
        "all_domains": False,
        "service_host": SERVICE_HOST,
        "format": "human",
        "nameserver": None,
        "port": 53,
        "timeout": 2.0,
        "workers": 4,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_dns_help_lists_records_and_read_only_check() -> None:
    parser = build_parser()
    dns_parser = next(
        action.choices["dns"]
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert "check" in dns_parser.format_help()
    assert "read-only" in dns_parser.format_help()


def test_checker_accepts_exact_records_and_canonical_address() -> None:
    report = DNSContractChecker(FakeDNSResolver(exact_records())).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 0
    assert report.status == "passed"
    assert report.summary == {
        "lookup-error": 0,
        "mismatched": 0,
        "missing": 0,
        "passed": 6,
    }
    assert report.checks[0].name == SERVICE_HOST
    assert report.checks[0].type == "A/AAAA"
    assert all(check.status == "passed" for check in report.checks)


def test_checker_distinguishes_missing_mismatched_and_indirect_aliases() -> None:
    records = exact_records()
    records.pop(("autoconfig.example.test", "CNAME"))
    records[("autodiscover.example.test", "CNAME")] = ("wrong.example.net.",)
    report = DNSContractChecker(
        FakeDNSResolver(
            records,
            aliases={
                ("_ua-auto-config.example.test", "TXT"): "shared.example.net",
            },
        )
    ).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 1
    assert report.status == "failed"
    statuses = {(check.name, check.type): check.status for check in report.checks}
    assert statuses[("autoconfig.example.test", "CNAME")] == "missing"
    assert statuses[("autodiscover.example.test", "CNAME")] == "mismatched"
    assert statuses[("_ua-auto-config.example.test", "TXT")] == "mismatched"
    conflict = next(
        check for check in report.checks if check.name == "_ua-auto-config.example.test"
    )
    assert conflict.actual[0] == "CNAME -> shared.example.net."
    assert "requires direct TXT data" in conflict.detail


def test_indirect_alias_without_target_data_is_drift_not_missing() -> None:
    records = exact_records()
    records.pop(("_ua-auto-config.example.test", "TXT"))
    report = DNSContractChecker(
        FakeDNSResolver(
            records,
            aliases={
                ("_ua-auto-config.example.test", "TXT"): "shared.example.net",
            },
        )
    ).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    conflict = next(
        check for check in report.checks if check.name == "_ua-auto-config.example.test"
    )
    assert conflict.status == "mismatched"
    assert conflict.actual == ("CNAME -> shared.example.net.",)


@pytest.mark.parametrize(
    "published",
    [
        "v=UAAC1;a=sha256;d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=",
        "d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=;a=sha256;v=UAAC1",
        "v = UAAC1 ; a = sha256 ; d = x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE= ; ",
        "v=UAAC1; x=ignored; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=",
        "v=UAAC1; x=one; x=two; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=",
        "v=UAAC1; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxF=",
    ],
)
def test_pacc_txt_comparison_accepts_draft_equivalent_records(published: str) -> None:
    records = exact_records()
    records[("_ua-auto-config.example.test", "TXT")] = (published,)

    report = DNSContractChecker(FakeDNSResolver(records)).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 0
    pacc = next(check for check in report.checks if check.type == "TXT")
    assert pacc.status == "passed"


@pytest.mark.parametrize(
    "published",
    [
        " v=UAAC1; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=",
        "v=uaac1; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=",
        "v=UAAC1; a=sha256",
        "v=UAAC1; a=sha256; d=not-base64!",
        "v=UAAC1; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE=",
    ],
)
def test_pacc_txt_comparison_rejects_malformed_records(published: str) -> None:
    records = exact_records()
    records[("_ua-auto-config.example.test", "TXT")] = (published,)

    report = DNSContractChecker(FakeDNSResolver(records)).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 1
    assert next(check for check in report.checks if check.type == "TXT").status == "mismatched"


def test_required_txt_and_srv_values_may_coexist_with_additional_records() -> None:
    records = exact_records()
    records[("_ua-auto-config.example.test", "TXT")] += (
        "v=UAAC1; a=sha256; d=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    )
    records[("_autodiscover._tcp.example.test", "SRV")] += (
        "10 0 443 backup.example.net.",
    )

    report = DNSContractChecker(FakeDNSResolver(records)).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 0
    assert next(check for check in report.checks if check.type == "TXT").status == "passed"
    assert next(check for check in report.checks if check.type == "SRV").status == "passed"


def test_checker_rejects_canonical_cname_and_reports_lookup_errors() -> None:
    records = exact_records()
    records[(SERVICE_HOST, "CNAME")] = ("elsewhere.example.net.",)
    report = DNSContractChecker(
        FakeDNSResolver(
            records,
            errors={("_autodiscover._tcp.example.test", "SRV")},
        )
    ).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 2
    assert report.status == "error"
    assert report.checks[0].status == "mismatched"
    assert "must not be a CNAME" in report.checks[0].detail
    lookup = next(check for check in report.checks if check.type == "SRV")
    assert lookup.status == "lookup-error"
    assert lookup.actual == ()


def test_canonical_partial_address_lookup_is_an_error() -> None:
    report = DNSContractChecker(
        FakeDNSResolver(exact_records(), errors={(SERVICE_HOST, "AAAA")})
    ).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 2
    assert report.status == "error"
    assert report.checks[0].status == "lookup-error"
    assert report.checks[0].actual == ("A 192.0.2.10",)
    assert "AAAA lookup failed" in report.checks[0].detail


def test_canonical_host_without_address_data_is_missing() -> None:
    records = exact_records()
    records.pop((SERVICE_HOST, "A"))

    report = DNSContractChecker(FakeDNSResolver(records)).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 1
    assert report.checks[0].status == "missing"
    assert "neither A nor AAAA" in report.checks[0].detail


def test_canonical_cname_lookup_failure_is_an_error() -> None:
    report = DNSContractChecker(
        FakeDNSResolver(exact_records(), errors={(SERVICE_HOST, "CNAME")})
    ).check(
        config_path=str(CONFIG),
        domains=("example.test",),
        service_host=SERVICE_HOST,
    )

    assert report.exit_code == 2
    assert report.checks[0].status == "lookup-error"
    assert "canonical CNAME lookup failed" in report.checks[0].detail


def test_check_json_is_deterministic_machine_readable_and_read_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = check_arguments(format="json")
    resolver = FakeDNSResolver(exact_records())

    assert run_check(args, resolver=resolver) == 0
    first = capsys.readouterr().out
    assert run_check(args, resolver=resolver) == 0
    assert capsys.readouterr().out == first
    document = json.loads(first)
    assert document["mode"] == "read-only"
    assert document["resolver"] == "fake resolver"
    assert document["domains"] == ["example.test"]
    assert document["status"] == "passed"
    assert document["summary"]["passed"] == 6


def test_check_human_output_has_operator_markers_and_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    records = exact_records()
    records.pop(("autoconfig.example.test", "CNAME"))

    assert run_check(check_arguments(), resolver=FakeDNSResolver(records)) == 1
    output = capsys.readouterr().out
    assert "DNS contract check (read-only)" in output
    assert "[PASS]" in output
    assert "[MISS] autoconfig.example.test CNAME" in output
    assert "expected: automx.example.net." in output
    assert "Result: failed" in output


def test_check_defaults_to_all_configured_domains(tmp_path: Path) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        CONFIG.read_text(encoding="utf-8").replace(
            "domains = example.test", "domains = example.test, second.test"
        ),
        encoding="utf-8",
    )
    records = exact_records()
    records.update(exact_records("second.test"))
    report = DNSContractChecker(FakeDNSResolver(records)).check_from_arguments(
        check_arguments(config=str(config))
    )

    assert report.domains == ("example.test", "second.test")
    assert report.exit_code == 0
    assert report.summary["passed"] == 11


def test_records_can_emit_all_domains_without_changing_single_domain_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        CONFIG.read_text(encoding="utf-8").replace(
            "domains = example.test", "domains = example.test, second.test"
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "dns",
                "records",
                "--config",
                str(config),
                "--service-host",
                SERVICE_HOST,
                "--all-domains",
                "--format",
                "json",
            ]
        )
        == 0
    )
    document = json.loads(capsys.readouterr().out)
    assert document["mode"] == "read-only"
    assert document["domains"] == ["example.test", "second.test"]
    assert len(document["records"]) == 10
    assert {record["domain"] for record in document["records"]} == {
        "example.test",
        "second.test",
    }


def test_wildcard_configuration_requires_explicit_domain_for_check(tmp_path: Path) -> None:
    config = tmp_path / "automx.conf"
    config.write_text(
        CONFIG.read_text(encoding="utf-8").replace(
            "domains = example.test", "domains = *"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="--domain is required"):
        DNSContractChecker(FakeDNSResolver(exact_records())).check_from_arguments(
            check_arguments(config=str(config))
        )


def test_record_model_normalizes_zone_output() -> None:
    assert DNSRecord("Alias.Example", "CNAME", "Target.Example.").zone_line(300) == (
        "Alias.Example. 300 IN CNAME Target.Example."
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"nameservers": ("resolver.example",), "port": 53, "timeout": 2}, "--nameserver"),
        ({"nameservers": (), "port": 0, "timeout": 2}, "--port"),
        ({"nameservers": (), "port": 53, "timeout": 31}, "--timeout"),
        ({"nameservers": ("192.0.2.1",) * 9, "port": 53, "timeout": 2}, "--nameserver"),
    ],
)
def test_dnspython_resolver_rejects_unbounded_or_ambiguous_options(
    arguments: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        DnspythonDNSResolver(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("workers", [0, 33])
def test_checker_rejects_unbounded_worker_counts(workers: int) -> None:
    with pytest.raises(ValueError, match="--workers"):
        DNSRecordChecker(FakeDNSResolver(exact_records()), workers=workers)


@pytest.mark.parametrize("hostname", ["", "bad name.example", "a" * 64 + ".example"])
def test_hostname_normalization_rejects_invalid_names(hostname: str) -> None:
    with pytest.raises(ValueError, match="must be a DNS hostname"):
        normalize_hostname(hostname, option="test name")


@pytest.mark.parametrize(
    ("record_type", "value"),
    [("A", "2001:db8::1"), ("AAAA", "192.0.2.1")],
)
def test_address_normalization_rejects_the_wrong_family(
    record_type: str,
    value: str,
) -> None:
    with pytest.raises(DNSLookupError, match=f"invalid {record_type} answer"):
        normalize_rdata(record_type, value)


class FakeRdata:
    def __init__(self, text: str, *, strings: tuple[bytes, ...] | None = None) -> None:
        self.text = text
        if strings is not None:
            self.strings = strings

    def to_text(self) -> str:
        return self.text


class FakeAnswer(list[FakeRdata]):
    def __init__(
        self,
        *items: FakeRdata,
        has_rrset: bool = True,
        canonical_name: str | None = None,
    ) -> None:
        super().__init__(items)
        self.rrset = object() if has_rrset else None
        if canonical_name is not None:
            self.canonical_name = canonical_name


def test_dnspython_adapter_normalizes_answers_and_applies_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[object] = []

    class NativeResolver:
        def __init__(self, *, configure: bool) -> None:
            self.configure = configure
            self.nameservers: list[str] = []
            self.port = 0
            self.timeout = 0.0
            self.lifetime = 0.0
            instances.append(self)

        def resolve(
            self,
            _name: str,
            record_type: str,
            **_kwargs: object,
        ) -> FakeAnswer:
            if record_type == "TXT":
                return FakeAnswer(FakeRdata("ignored", strings=(b"part", b"two")))
            return FakeAnswer(FakeRdata("Target.Example."), FakeRdata("target.example."))

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", NativeResolver)
    resolver = DnspythonDNSResolver(
        nameservers=("192.0.2.53", "198.51.100.53"),
        port=1053,
        timeout=2,
    )

    assert resolver.lookup("alias.example", "CNAME") == DNSAnswer(
        values=("target.example.",),
        canonical_name="alias.example",
    )
    assert resolver.lookup("txt.example", "TXT") == DNSAnswer(
        values=("parttwo",),
        canonical_name="txt.example",
    )
    native = instances[0]
    assert native.configure is False  # type: ignore[attr-defined]
    assert native.nameservers == ["192.0.2.53", "198.51.100.53"]  # type: ignore[attr-defined]
    assert native.port == 1053  # type: ignore[attr-defined]
    assert native.timeout == 2  # type: ignore[attr-defined]
    assert native.lifetime == 4  # type: ignore[attr-defined]


def test_dnspython_adapter_ignores_non_utf8_txt_sibling_for_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    digest = b"v=UAAC1; a=sha256; d=x4UCWvDe1w8ERAAFF8yaWut70DP8PNqw+p0oRsr6zxE="

    class NativeResolver:
        def __init__(self, *, configure: bool) -> None:
            self.nameservers: list[str] = []
            self.port = 0
            self.timeout = 0.0
            self.lifetime = 0.0

        def resolve(self, *_args: object, **_kwargs: object) -> FakeAnswer:
            return FakeAnswer(
                FakeRdata("ignored", strings=(digest,)),
                FakeRdata("ignored", strings=(b"\xff\xfe",)),
            )

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", NativeResolver)
    resolver = DnspythonDNSResolver(nameservers=(), port=53, timeout=2)

    assert resolver.lookup("_ua-auto-config.example.test", "TXT") == DNSAnswer(
        ("<invalid non-ASCII TXT data>", digest.decode("ascii")),
        "_ua-auto-config.example.test",
    )


def test_dnspython_adapter_preserves_alias_provenance_without_target_rrset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NativeResolver:
        def __init__(self, *, configure: bool) -> None:
            self.nameservers: list[str] = []
            self.port = 0
            self.timeout = 0.0
            self.lifetime = 0.0

        def resolve(self, *_args: object, **_kwargs: object) -> FakeAnswer:
            return FakeAnswer(
                has_rrset=False,
                canonical_name="shared.example.net.",
            )

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", NativeResolver)
    resolver = DnspythonDNSResolver(nameservers=(), port=53, timeout=2)

    assert resolver.lookup("alias.example", "TXT") == DNSAnswer(
        (),
        "shared.example.net",
    )


def test_dnspython_adapter_preserves_alias_provenance_from_nxdomain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_name = dns.name.from_text("alias.example.")

    class NXResponse:
        def canonical_name(self) -> dns.name.Name:
            return dns.name.from_text("shared.example.net.")

    exception = dns_contracts.dns.resolver.NXDOMAIN(
        qnames=[query_name],
        responses={query_name: NXResponse()},
    )

    class NativeResolver:
        def __init__(self, *, configure: bool) -> None:
            self.nameservers: list[str] = []
            self.port = 0
            self.timeout = 0.0
            self.lifetime = 0.0

        def resolve(self, *_args: object, **_kwargs: object) -> FakeAnswer:
            raise exception

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", NativeResolver)
    resolver = DnspythonDNSResolver(nameservers=(), port=53, timeout=2)

    assert resolver.lookup("alias.example", "TXT") == DNSAnswer(
        (),
        "shared.example.net",
    )


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (dns_contracts.dns.resolver.NXDOMAIN(), ()),
        (dns_contracts.dns.exception.Timeout(), DNSLookupError),
    ],
)
def test_dnspython_adapter_distinguishes_absence_from_lookup_failure(
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected: tuple[()] | type[DNSLookupError],
) -> None:
    class NativeResolver:
        def __init__(self, *, configure: bool) -> None:
            self.nameservers: list[str] = []
            self.port = 0
            self.timeout = 0.0
            self.lifetime = 0.0

        def resolve(self, *_args: object, **_kwargs: object) -> FakeAnswer:
            raise exception

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", NativeResolver)
    resolver = DnspythonDNSResolver(nameservers=(), port=53, timeout=2)

    if expected == ():
        assert resolver.lookup("missing.example", "A") == DNSAnswer((), "missing.example")
    else:
        with pytest.raises(expected):
            resolver.lookup("broken.example", "A")


def test_dnspython_adapter_contains_invalid_wire_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NativeResolver:
        def __init__(self, *, configure: bool) -> None:
            self.nameservers: list[str] = []
            self.port = 0
            self.timeout = 0.0
            self.lifetime = 0.0

        def resolve(self, *_args: object, **_kwargs: object) -> FakeAnswer:
            return FakeAnswer(FakeRdata("0 0 443 invalid target"))

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", NativeResolver)
    resolver = DnspythonDNSResolver(nameservers=(), port=53, timeout=2)

    with pytest.raises(DNSLookupError, match="invalid SRV answer"):
        resolver.lookup("_service._tcp.example", "SRV")


def test_dnspython_adapter_accepts_root_srv_target_as_wire_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NativeResolver:
        def __init__(self, *, configure: bool) -> None:
            self.nameservers: list[str] = []
            self.port = 0
            self.timeout = 0.0
            self.lifetime = 0.0

        def resolve(self, *_args: object, **_kwargs: object) -> FakeAnswer:
            return FakeAnswer(FakeRdata("0 0 0 ."))

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", NativeResolver)
    resolver = DnspythonDNSResolver(nameservers=(), port=53, timeout=2)

    assert resolver.lookup("_service._tcp.example", "SRV") == DNSAnswer(
        values=("0 0 0 .",),
        canonical_name="_service._tcp.example",
    )


def test_dnspython_adapter_contains_missing_system_resolver_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_resolver(*, configure: bool) -> object:
        raise dns_contracts.dns.resolver.NoResolverConfiguration

    monkeypatch.setattr(dns_contracts.dns.resolver, "Resolver", fail_resolver)
    resolver = DnspythonDNSResolver(nameservers=(), port=53, timeout=2)

    with pytest.raises(DNSLookupError, match="NoResolverConfiguration"):
        resolver.lookup("example.test", "A")
