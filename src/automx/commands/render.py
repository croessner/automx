"""Render exact local protocol documents without network access."""

from __future__ import annotations

import argparse
import sys

from automx.commands.common import DEFAULT_CONFIG, repository, selected_domain
from automx.documents import (
    autoconfig_document,
    autodiscover_document,
    mobileconfig_document_result,
    pacc_document,
)
from automx.renderers.autodiscover import AutodiscoverSchema


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "render",
        help="write exact local protocol document bytes",
    )
    commands = parser.add_subparsers(dest="render_command", required=True)

    autoconfig = commands.add_parser(
        "autoconfig",
        help="render Mail Autoconfig for a synthetic address",
    )
    _add_email_options(autoconfig)
    autoconfig.set_defaults(handler=run_autoconfig)

    autodiscover = commands.add_parser(
        "autodiscover",
        help="render one Microsoft Autodiscover response schema",
    )
    _add_email_options(autodiscover)
    autodiscover.add_argument(
        "--schema",
        required=True,
        choices=("outlook", "mobilesync"),
        help="response schema to render",
    )
    autodiscover.set_defaults(handler=run_autodiscover)

    mobileconfig = commands.add_parser(
        "mobileconfig",
        help="render a password-free Apple Mail configuration profile",
    )
    _add_email_options(mobileconfig)
    mobileconfig.add_argument(
        "--common-name",
        help="optional display name for the generated mail account",
    )
    mobileconfig.add_argument(
        "--signature-status",
        action="store_true",
        help="report CMS integrity to stderr without changing profile bytes",
    )
    mobileconfig.set_defaults(handler=run_mobileconfig)

    pacc = commands.add_parser("pacc", help="render PACC-03 JSON for a domain")
    pacc.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    pacc.add_argument("--domain", required=True, help="configured domain to render")
    pacc.set_defaults(handler=run_pacc)


def _add_email_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    parser.add_argument(
        "--email",
        required=True,
        help="synthetic address used for profile resolution",
    )


def _write(body: bytes) -> int:
    sys.stdout.buffer.write(body)
    return 0


def run_autoconfig(args: argparse.Namespace) -> int:
    return _write(autoconfig_document(repository(args.config), args.email))


def run_autodiscover(args: argparse.Namespace) -> int:
    schema = (
        AutodiscoverSchema.OUTLOOK
        if args.schema == "outlook"
        else AutodiscoverSchema.MOBILE
    )
    return _write(autodiscover_document(repository(args.config), args.email, schema))


def run_mobileconfig(args: argparse.Namespace) -> int:
    result = mobileconfig_document_result(
        repository(args.config),
        args.email,
        common_name=args.common_name,
    )
    if args.signature_status:
        if result.signature.signed:
            print(
                "automx: mobileconfig signature: valid; "
                f"signer-sha256={result.signature.signer_sha256}; "
                "trust: device-dependent",
                file=sys.stderr,
            )
        else:
            print("automx: mobileconfig signature: unsigned", file=sys.stderr)
    return _write(result.body)


def run_pacc(args: argparse.Namespace) -> int:
    config_repository = repository(args.config)
    domain = selected_domain(config_repository, args.domain)
    return _write(pacc_document(config_repository, domain))
