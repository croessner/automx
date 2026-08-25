"""Read-only DNS resolution and normalized contract comparison primitives."""

from __future__ import annotations

import base64
import binascii
import ipaddress
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from typing import Any, Protocol, cast

import dns.exception
import dns.resolver

_RECORD_TYPES = ("CNAME", "SRV", "TXT", "A", "AAAA")
_RESULT_STATUSES = ("lookup-error", "mismatched", "missing", "passed")
_MAX_NAMESERVERS = 8


@dataclass(frozen=True, slots=True)
class DNSRecord:
    name: str
    type: str
    value: str

    def zone_line(self, ttl: int) -> str:
        value = f'"{self.value}"' if self.type == "TXT" else self.value
        return f"{self.name}. {ttl} IN {self.type} {value}"


@dataclass(frozen=True, slots=True)
class DNSCheck:
    """One normalized required-owner comparison."""

    domain: str | None
    name: str
    type: str
    expected: tuple[str, ...]
    actual: tuple[str, ...]
    status: str
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DNSAnswer:
    """Normalized answer values plus CNAME-chain provenance."""

    values: tuple[str, ...]
    canonical_name: str


@dataclass(frozen=True, slots=True)
class DNSCheckReport:
    """Deterministic read-only result with drift and operational exit codes."""

    domains: tuple[str, ...]
    service_host: str
    resolver: str
    checks: tuple[DNSCheck, ...]

    @property
    def summary(self) -> dict[str, int]:
        counts = Counter(check.status for check in self.checks)
        return {status: counts[status] for status in _RESULT_STATUSES}

    @property
    def status(self) -> str:
        if self.summary["lookup-error"]:
            return "error"
        if self.summary["missing"] or self.summary["mismatched"]:
            return "failed"
        return "passed"

    @property
    def exit_code(self) -> int:
        if self.status == "error":
            return 2
        if self.status == "failed":
            return 1
        return 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "checks": [check.as_dict() for check in self.checks],
            "domains": self.domains,
            "mode": "read-only",
            "resolver": self.resolver,
            "service_host": self.service_host,
            "status": self.status,
            "summary": self.summary,
        }


class DNSLookupError(ValueError):
    """A DNS answer could not be obtained, as distinct from an empty answer."""


class DNSResolver(Protocol):
    """Injectable, side-effect-free DNS lookup boundary."""

    description: str

    def lookup(self, name: str, record_type: str) -> DNSAnswer: ...


class DnspythonDNSResolver:
    """Bounded dnspython resolver using the system view or an explicit server pool."""

    def __init__(
        self,
        *,
        nameservers: tuple[str, ...],
        port: int,
        timeout: float,
    ) -> None:
        if not 0 < timeout <= 30:
            raise ValueError("--timeout must be between 0 and 30 seconds")
        if not 1 <= port <= 65_535:
            raise ValueError("--port must be between 1 and 65535")
        if len(nameservers) > _MAX_NAMESERVERS:
            raise ValueError(f"--nameserver may be repeated at most {_MAX_NAMESERVERS} times")
        normalized_nameservers: list[str] = []
        for nameserver in nameservers:
            try:
                normalized_nameservers.append(str(ipaddress.ip_address(nameserver)))
            except ValueError as exc:
                raise ValueError("--nameserver must be an IPv4 or IPv6 address") from exc
        self.nameservers = tuple(normalized_nameservers)
        self.port = port
        self.timeout = timeout
        self.description = (
            f"explicit resolver pool {', '.join(self.nameservers)} port {self.port}"
            if self.nameservers
            else f"system resolver port {self.port}"
        )

    def lookup(self, name: str, record_type: str) -> DNSAnswer:
        if record_type not in _RECORD_TYPES:
            raise ValueError(f"unsupported DNS record type: {record_type}")
        query_name = normalize_hostname(name, option="DNS query name")
        try:
            resolver = dns.resolver.Resolver(configure=not self.nameservers)
            if self.nameservers:
                resolver.nameservers = list(self.nameservers)
            resolver.port = self.port
            resolver.timeout = self.timeout
            attempts = max(1, min(len(resolver.nameservers), _MAX_NAMESERVERS))
            resolver.lifetime = self.timeout * attempts
            answer = resolver.resolve(
                query_name,
                record_type,
                search=False,
                raise_on_no_answer=False,
            )
        except dns.resolver.NXDOMAIN as exc:
            try:
                canonical_name = normalize_hostname(
                    str(exc.canonical_name),
                    option="canonical answer name",
                )
            except TypeError:
                canonical_name = query_name
            except (UnicodeError, ValueError) as name_error:
                raise DNSLookupError(f"invalid {record_type} answer") from name_error
            return DNSAnswer((), canonical_name)
        except dns.resolver.NoAnswer:
            return DNSAnswer((), query_name)
        except dns.exception.DNSException as exc:
            raise DNSLookupError(type(exc).__name__) from exc
        try:
            canonical_name = normalize_hostname(
                str(getattr(answer, "canonical_name", query_name)),
                option="canonical answer name",
            )
            if answer.rrset is None:
                return DNSAnswer((), canonical_name)
            values = {_rdata_text(record_type, cast(Any, item)) for item in answer}
        except DNSLookupError:
            raise
        except (UnicodeError, ValueError) as exc:
            raise DNSLookupError(f"invalid {record_type} answer") from exc
        return DNSAnswer(tuple(sorted(values)), canonical_name)


def normalize_hostname(value: str, *, option: str) -> str:
    """Return a lowercase IDNA hostname without a trailing root label."""

    candidate = value.rstrip(".").lower()
    if not candidate or len(candidate) > 253 or any(char.isspace() for char in candidate):
        raise ValueError(f"{option} must be a DNS hostname")
    try:
        labels = tuple(label.encode("idna").decode("ascii") for label in candidate.split("."))
    except UnicodeError as exc:
        raise ValueError(f"{option} must be a DNS hostname") from exc
    if any(not label or len(label) > 63 for label in labels):
        raise ValueError(f"{option} must be a DNS hostname")
    return ".".join(labels)


def normalize_rdata(record_type: str, value: str) -> str:
    """Normalize comparable RDATA without changing TXT contract bytes."""

    if record_type == "CNAME":
        if value == ".":
            return "."
        return f"{normalize_hostname(value, option='CNAME target')}."
    if record_type == "SRV":
        fields = value.split()
        if len(fields) != 4:
            raise DNSLookupError("invalid SRV answer")
        try:
            priority, weight, port = (int(field) for field in fields[:3])
        except ValueError as exc:
            raise DNSLookupError("invalid SRV answer") from exc
        if any(number < 0 or number > 65_535 for number in (priority, weight, port)):
            raise DNSLookupError("invalid SRV answer")
        target = (
            "."
            if fields[3] == "."
            else f"{normalize_hostname(fields[3], option='SRV target')}."
        )
        return f"{priority} {weight} {port} {target}"
    if record_type in {"A", "AAAA"}:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise DNSLookupError(f"invalid {record_type} answer") from exc
        expected_version = 4 if record_type == "A" else 6
        if address.version != expected_version:
            raise DNSLookupError(f"invalid {record_type} answer")
        return str(address)
    if record_type == "TXT":
        return value
    raise ValueError(f"unsupported DNS record type: {record_type}")


def _rdata_text(record_type: str, item: Any) -> str:
    if record_type == "TXT":
        chunks = cast(tuple[bytes, ...] | None, getattr(item, "strings", None))
        if chunks is None:
            raise DNSLookupError("unsupported TXT answer representation")
        try:
            return b"".join(chunks).decode("utf-8")
        except UnicodeDecodeError:
            # A malformed sibling must not hide a valid PACC record in the
            # same RRset.  Preserve it as an unmatchable value so the checker
            # can still evaluate every other TXT record.
            return "<invalid non-ASCII TXT data>"
    return normalize_rdata(record_type, cast(str, item.to_text()))


def _pacc_sha256_digest(value: str) -> bytes | None:
    """Parse one UAAC1 TXT RR according to PACC-03 section 5.2.2.2."""

    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return None
    candidate = value.rstrip(" \t")
    if candidate.endswith(";"):
        candidate = candidate[:-1].rstrip(" \t")
    if not candidate or candidate[0] in " \t":
        return None

    tags: dict[str, str] = {}
    for raw_specification in candidate.split(";"):
        specification = raw_specification.strip(" \t")
        name, separator, tag_value = specification.partition("=")
        name = name.rstrip(" \t")
        tag_value = tag_value.lstrip(" \t")
        if (
            not separator
            or not name
            or not tag_value
            or not name.isascii()
            or not name.isalnum()
            or any(not 0x21 <= ord(character) <= 0x7E for character in tag_value)
            or ";" in tag_value
        ):
            return None
        if name in {"v", "a", "d"}:
            if name in tags:
                return None
            tags[name] = tag_value

    if tags.get("v") != "UAAC1" or tags.get("a") != "sha256" or "d" not in tags:
        return None
    encoded_digest = tags["d"]
    try:
        digest = base64.b64decode(encoded_digest, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(digest) != 32:
        return None
    return digest


_LookupResult = DNSAnswer | DNSLookupError


class DNSRecordChecker:
    """Compare generated records with one explicit DNS resolution view."""

    def __init__(self, resolver: DNSResolver, *, workers: int = 8) -> None:
        if not 1 <= workers <= 32:
            raise ValueError("--workers must be between 1 and 32")
        self.resolver = resolver
        self.workers = workers

    def check(
        self,
        *,
        domains: tuple[str, ...],
        service_host: str,
        records: tuple[tuple[str, DNSRecord], ...],
    ) -> DNSCheckReport:
        target = normalize_hostname(service_host, option="--service-host")
        queries = {(target, record_type) for record_type in ("CNAME", "A", "AAAA")}
        for _domain, record in records:
            queries.add((record.name, record.type))
        answers = self._lookups(queries)

        checks = [self._canonical_check(target, answers)]
        checks.extend(
            self._record_check(domain, record, answers)
            for domain, record in records
        )
        return DNSCheckReport(
            domains=tuple(normalize_hostname(domain, option="--domain") for domain in domains),
            service_host=target,
            resolver=self.resolver.description,
            checks=tuple(checks),
        )

    def _lookups(self, queries: set[tuple[str, str]]) -> dict[tuple[str, str], _LookupResult]:
        results: dict[tuple[str, str], _LookupResult] = {}

        def lookup(query: tuple[str, str]) -> _LookupResult:
            try:
                return self.resolver.lookup(*query)
            except DNSLookupError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="automx-dns") as pool:
            futures = {pool.submit(lookup, query): query for query in queries}
            for future in as_completed(futures):
                results[futures[future]] = future.result()
        return results

    @staticmethod
    def _canonical_check(
        service_host: str,
        answers: dict[tuple[str, str], _LookupResult],
    ) -> DNSCheck:
        cname = answers[(service_host, "CNAME")]
        addresses: list[str] = []
        address_errors: list[tuple[str, DNSLookupError]] = []
        for record_type in ("A", "AAAA"):
            answer = answers[(service_host, record_type)]
            if isinstance(answer, DNSLookupError):
                address_errors.append((record_type, answer))
            else:
                addresses.extend(f"{record_type} {value}" for value in answer.values)
        expected = ("at least one A or AAAA record and no CNAME",)
        if isinstance(cname, DNSLookupError):
            return DNSCheck(
                None,
                service_host,
                "A/AAAA",
                expected,
                tuple(sorted(addresses)),
                "lookup-error",
                f"canonical CNAME lookup failed: {cname}",
            )
        if cname.values:
            return DNSCheck(
                None,
                service_host,
                "A/AAAA",
                expected,
                cname.values,
                "mismatched",
                "canonical service host must not be a CNAME",
            )
        if address_errors:
            return DNSCheck(
                None,
                service_host,
                "A/AAAA",
                expected,
                tuple(sorted(addresses)),
                "lookup-error",
                "; ".join(
                    f"{record_type} lookup failed: {error}"
                    for record_type, error in address_errors
                ),
            )
        if addresses:
            return DNSCheck(
                None,
                service_host,
                "A/AAAA",
                expected,
                tuple(sorted(addresses)),
                "passed",
                "canonical service host has address data and no CNAME",
            )
        return DNSCheck(
            None,
            service_host,
            "A/AAAA",
            expected,
            (),
            "missing",
            "canonical service host has neither A nor AAAA data",
        )

    @staticmethod
    def _record_check(
        domain: str,
        record: DNSRecord,
        answers: dict[tuple[str, str], _LookupResult],
    ) -> DNSCheck:
        expected = (normalize_rdata(record.type, record.value),)
        answer = answers[(record.name, record.type)]
        if isinstance(answer, DNSLookupError):
            return DNSCheck(
                domain,
                record.name,
                record.type,
                expected,
                (),
                "lookup-error",
                f"{record.type} lookup failed: {answer}",
            )
        if record.type != "CNAME" and answer.canonical_name != record.name:
            alias = f"{answer.canonical_name}."
            return DNSCheck(
                domain,
                record.name,
                record.type,
                expected,
                (f"CNAME -> {alias}", *answer.values),
                "mismatched",
                f"owner resolves through CNAME; generated contract requires direct {record.type} data",
            )
        if not answer.values:
            return DNSCheck(
                domain,
                record.name,
                record.type,
                expected,
                (),
                "missing",
                "required DNS record is missing",
            )
        if record.type == "TXT":
            expected_digest = _pacc_sha256_digest(expected[0])
            if expected_digest is None:  # generated exclusively by pacc_digest_record()
                raise DNSLookupError("generated PACC TXT contract is invalid")
            matches = any(
                _pacc_sha256_digest(value) == expected_digest for value in answer.values
            )
        elif record.type == "SRV":
            matches = expected[0] in answer.values
        else:
            matches = answer.values == expected
        if not matches:
            return DNSCheck(
                domain,
                record.name,
                record.type,
                expected,
                answer.values,
                "mismatched",
                "published DNS data differs from the generated contract",
            )
        return DNSCheck(
            domain,
            record.name,
            record.type,
            expected,
            answer.values,
            "passed",
            "published DNS data contains the generated contract",
        )
