from __future__ import annotations

import re
from pathlib import Path

from automx.commands.dns import deployment_records
from automx.configuration import ConfigurationRepository

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "contrib/node1/automx.conf"
DNS_PLAN = ROOT / "contrib/node1/dns-plan.txt"
DOMAINS = (
    "itsi.be",
    "dsgvo-europa.de",
    "ra-roessner-merle.de",
    "iladresse.de",
    "emailforschung.de",
    "dsb-in-hessen.de",
    "alltagswahnsinn.de",
    "dsb-roessner.de",
    "christianroessner.de",
    "exampleserver.de",
    "nicoleschuldt.de",
    "roessner-net.de",
    "roessner.blog",
    "nauthilus.org",
    "mlserv.org",
    "alsfeld.email",
    "roessner.email",
    "roessner-network-solutions.com",
    "nauthilus.com",
    "roessner-net.com",
    "roessner.co",
    "mymail.zip",
    "roessner.services",
    "nauthilus.net",
    "srvint.net",
    "roessner.support",
)
EXCLUDED_MX_ZONES = (
    "roessner.cloud",
    "dsgvo-roessner.de",
    "nauthilus.de",
    "authserv.me",
    "roessner.website",
    "ra-roessner-merle.com",
    "authserv.net",
)
SERVICE_HOST = "autoconfig.roessner-net.de"


def test_node1_configuration_and_traefik_cover_exactly_the_live_mail_domains() -> None:
    repository = ConfigurationRepository.from_path(CONFIG)
    compose = (ROOT / "contrib/node1/compose.yaml").read_text(encoding="utf-8")

    assert repository.domains == DOMAINS
    for prefix in ("autoconfig", "autodiscover", "ua-auto-config"):
        assert tuple(re.findall(rf"Host\(`{prefix}\.([^`]+)`\)", compose)) == DOMAINS
    for domain in EXCLUDED_MX_ZONES:
        assert domain not in repository.domains


def test_node1_dns_plan_matches_the_production_pacc_bytes() -> None:
    lines = [
        "; Canonical host prerequisite (managed separately):",
        "; autoconfig.roessner-net.de. A/AAAA -> node1 public addresses",
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
    assert "autoconfig.roessner-net.de. 300 IN CNAME autoconfig.roessner-net.de." not in lines
