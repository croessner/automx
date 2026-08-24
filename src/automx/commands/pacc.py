"""Render PACC deployment material."""

from __future__ import annotations

import argparse

from automx.commands.common import DEFAULT_CONFIG, repository, selected_domain
from automx.renderers.pacc import pacc_digest_record, render_pacc


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("pacc", help="work with PACC-02 documents")
    commands = parser.add_subparsers(dest="pacc_command", required=True)
    digest = commands.add_parser("digest", help="print the UAAC1 DNS TXT value")
    digest.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    digest.add_argument("--domain", help="domain to resolve")
    digest.set_defaults(handler=run_digest)


def pacc_bytes(config_path: str, domain: str | None) -> tuple[str, bytes]:
    config_repository = repository(config_path)
    selected = selected_domain(config_repository, domain)
    return selected, render_pacc(config_repository.resolve(f"pacc@{selected}"))


def run_digest(args: argparse.Namespace) -> int:
    _domain, body = pacc_bytes(args.config, args.domain)
    print(pacc_digest_record(body))
    return 0
