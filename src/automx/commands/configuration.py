"""Validate the service configuration without starting a server."""

from __future__ import annotations

import argparse

from automx.commands.common import DEFAULT_CONFIG, repository, selected_domain


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("config", help="inspect service configuration")
    commands = parser.add_subparsers(dest="config_command", required=True)
    validate = commands.add_parser("validate", help="validate and resolve a domain profile")
    validate.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    validate.add_argument("--domain", help="domain to resolve")
    validate.set_defaults(handler=run_validate)


def run_validate(args: argparse.Namespace) -> int:
    config_repository = repository(args.config)
    domain = selected_domain(config_repository, args.domain)
    config_repository.resolve(f"validate@{domain}")
    print(f"Configuration valid for {domain}.")
    return 0
