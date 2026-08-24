from __future__ import annotations

from pathlib import Path

from automx.commands.dns import deployment_records

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "contrib/node1/automx.conf"
DNS_PLAN = ROOT / "contrib/node1/dns-plan.txt"
DOMAINS = (
    "roessner-net.de",
    "alltagswahnsinn.de",
    "alsfeld.email",
    "ra-roessner-merle.de",
    "roessner-net.com",
    "roessner.email",
)
SERVICE_HOST = "autoconfig.roessner-net.de"


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
