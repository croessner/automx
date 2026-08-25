"""Generate and verify read-only DNS deployment records for automx protocols."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

from automx.commands.common import DEFAULT_CONFIG, repository, selected_domain
from automx.commands.pacc import pacc_bytes
from automx.dns_contracts import (
    DNSCheckReport,
    DNSLookupError,
    DnspythonDNSResolver,
    DNSRecord,
    DNSRecordChecker,
    DNSResolver,
    normalize_hostname,
)
from automx.renderers.pacc import pacc_digest_record


def _selected_domains(
    *,
    config_path: str,
    domain: str | None,
    all_domains: bool,
    default_all: bool,
) -> tuple[str, ...]:
    config_repository = repository(config_path)
    if domain is not None and all_domains:
        raise ValueError("--domain and --all-domains are mutually exclusive")
    if domain is not None:
        return (normalize_hostname(domain, option="--domain"),)
    if all_domains or default_all:
        domains = tuple(item for item in config_repository.domains if item != "*")
        if not domains:
            raise ValueError("--domain is required for wildcard configuration")
        return domains
    return (selected_domain(config_repository, None),)


def deployment_records(
    *, config_path: str, domain: str | None, service_host: str
) -> tuple[str, tuple[DNSRecord, ...]]:
    """Generate one domain's records from the exact local PACC bytes."""

    selected, body = pacc_bytes(config_path, domain)
    selected = normalize_hostname(selected, option="--domain")
    target = normalize_hostname(service_host, option="--service-host")
    records = tuple(
        record
        for record in (
            DNSRecord(f"autoconfig.{selected}", "CNAME", f"{target}."),
            DNSRecord(f"autodiscover.{selected}", "CNAME", f"{target}."),
            DNSRecord(f"_autodiscover._tcp.{selected}", "SRV", f"0 0 443 {target}."),
            DNSRecord(f"ua-auto-config.{selected}", "CNAME", f"{target}."),
            DNSRecord(
                f"_ua-auto-config.{selected}",
                "TXT",
                pacc_digest_record(body),
            ),
        )
        if record.type != "CNAME" or record.name != target
    )
    return selected, records


class DNSContractChecker:
    """Compose configuration-derived records with the generic DNS checker."""

    def __init__(self, resolver: DNSResolver, *, workers: int = 8) -> None:
        self.resolver = resolver
        self.workers = workers

    def check_from_arguments(self, args: argparse.Namespace) -> DNSCheckReport:
        domains = _selected_domains(
            config_path=args.config,
            domain=args.domain,
            all_domains=args.all_domains,
            default_all=True,
        )
        return DNSContractChecker(self.resolver, workers=args.workers).check(
            config_path=args.config,
            domains=domains,
            service_host=args.service_host,
        )

    def check(
        self,
        *,
        config_path: str,
        domains: tuple[str, ...],
        service_host: str,
    ) -> DNSCheckReport:
        generated: list[tuple[str, DNSRecord]] = []
        for domain in domains:
            selected, records = deployment_records(
                config_path=config_path,
                domain=domain,
                service_host=service_host,
            )
            generated.extend((selected, record) for record in records)
        return DNSRecordChecker(self.resolver, workers=self.workers).check(
            domains=domains,
            service_host=service_host,
            records=tuple(generated),
        )


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "dns", help="generate and verify read-only DNS deployment material"
    )
    commands = parser.add_subparsers(dest="dns_command", required=True)
    records = commands.add_parser("records", help="print required automx DNS records")
    _add_common_arguments(records)
    records.add_argument("--format", choices=("zone", "json"), default="zone")
    records.add_argument("--ttl", type=int, default=3600, help="zone output TTL")
    records.set_defaults(handler=run_records)

    check = commands.add_parser("check", help="verify published DNS records read-only")
    _add_common_arguments(check)
    check.add_argument("--format", choices=("human", "json"), default="human")
    check.add_argument(
        "--nameserver",
        action="append",
        help="IPv4 or IPv6 resolver address; repeat to form one resolver pool",
    )
    check.add_argument("--port", type=int, default=53, help="DNS server port")
    check.add_argument("--timeout", type=float, default=3, help="per-query timeout")
    check.add_argument("--workers", type=int, default=8, help="parallel DNS queries")
    check.set_defaults(handler=run_check)


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    domains = parser.add_mutually_exclusive_group()
    domains.add_argument("--domain", help="one domain to resolve or verify")
    domains.add_argument(
        "--all-domains",
        action="store_true",
        help="process every configured non-wildcard domain",
    )
    parser.add_argument("--service-host", required=True, help="canonical automx HTTPS host")


def run_records(args: argparse.Namespace) -> int:
    if not 60 <= args.ttl <= 604_800:
        raise ValueError("--ttl must be between 60 and 604800 seconds")
    domains = _selected_domains(
        config_path=args.config,
        domain=args.domain,
        all_domains=args.all_domains,
        default_all=False,
    )
    generated = tuple(
        deployment_records(
            config_path=args.config,
            domain=domain,
            service_host=args.service_host,
        )
        for domain in domains
    )
    if args.format == "json":
        if len(generated) == 1 and not args.all_domains:
            domain, records = generated[0]
            document: dict[str, Any] = {
                "domain": domain,
                "mode": "read-only",
                "records": [asdict(record) for record in records],
            }
        else:
            document = {
                "domains": [domain for domain, _records in generated],
                "mode": "read-only",
                "records": [
                    {"domain": domain, **asdict(record)}
                    for domain, records in generated
                    for record in records
                ],
            }
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print("; Generated by automx (read-only; review before applying)")
        for domain, records in generated:
            if len(generated) > 1:
                print(f"; domain={domain}")
            for record in records:
                print(record.zone_line(args.ttl))
    return 0


def run_check(args: argparse.Namespace, *, resolver: DNSResolver | None = None) -> int:
    if resolver is None:
        resolver = DnspythonDNSResolver(
            nameservers=tuple(args.nameserver or ()),
            port=args.port,
            timeout=args.timeout,
        )
    report = DNSContractChecker(resolver, workers=args.workers).check_from_arguments(args)
    if args.format == "json":
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        _print_human_report(report)
    return report.exit_code


def _print_human_report(report: DNSCheckReport) -> None:
    print("DNS contract check (read-only)")
    print(f"Resolver: {report.resolver}")
    print(f"Domains: {', '.join(report.domains)}")
    for check in report.checks:
        marker = {
            "passed": "PASS",
            "missing": "MISS",
            "mismatched": "DRIFT",
            "lookup-error": "ERROR",
        }[check.status]
        print(f"[{marker}] {check.name} {check.type}: {check.detail}")
        if check.status != "passed":
            print(f"  expected: {', '.join(check.expected) or '-'}")
            print(f"  actual: {', '.join(check.actual) or '-'}")
    summary = ", ".join(
        f"{status}={count}" for status, count in report.summary.items()
    )
    print(f"Result: {report.status} ({summary})")


__all__ = [
    "DNSContractChecker",
    "DNSLookupError",
    "DNSRecord",
    "deployment_records",
    "run_check",
]
