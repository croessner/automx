from __future__ import annotations

import re
from pathlib import Path

from automx.commands.dns import deployment_records
from automx.configuration import ConfigurationRepository

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "contrib/production-example"
CONFIG = EXAMPLE / "automx.conf"
DNS_PLAN = EXAMPLE / "dns-plan.txt"
DOMAINS = ("example.test", "example-mail.test")
SERVICE_HOST = "automx.example.test"


def test_production_example_uses_only_synthetic_domains() -> None:
    repository = ConfigurationRepository.from_path(CONFIG)
    compose = (EXAMPLE / "compose.yaml").read_text(encoding="utf-8")

    assert repository.domains == DOMAINS
    assert "registry.example.test/automx@sha256:" in (
        EXAMPLE / "automx.env.example"
    ).read_text(encoding="utf-8")
    for prefix in ("autoconfig", "autodiscover", "ua-auto-config"):
        assert tuple(re.findall(rf"Host\(`{prefix}\.([^`]+)`\)", compose)) == DOMAINS


def test_production_example_dns_plan_matches_rendered_pacc_bytes() -> None:
    lines = [
        "; Canonical host prerequisite (managed separately):",
        "; automx.example.test. A/AAAA -> deployment public addresses",
    ]
    for domain in DOMAINS:
        selected, records = deployment_records(
            config_path=str(CONFIG),
            domain=domain,
            service_host=SERVICE_HOST,
        )
        lines.append(f"; domain={selected}")
        lines.extend(record.zone_line(300) for record in records)

    assert DNS_PLAN.read_text(encoding="utf-8") == "\n".join(lines) + "\n"
    assert "automx.example.test. 300 IN CNAME automx.example.test." not in lines
