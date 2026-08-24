"""English command-line entry point for the automx operator toolkit."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from automx import __version__
from automx.commands import configuration, dns, openapi, pacc, probe, serve
from automx.configuration import ConfigurationError
from automx.renderers.pacc import PaccRenderError

Handler = Callable[[argparse.Namespace], int]


def build_parser() -> argparse.ArgumentParser:
    """Build the complete, side-effect-free CLI parser."""

    parser = argparse.ArgumentParser(
        prog="automx",
        description="Operate, validate, publish, and probe an automx service.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (serve, configuration, openapi, dns, pacc, probe):
        command.register(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one CLI command and map expected operator errors to exit status 2."""

    args = build_parser().parse_args(argv)
    handler: Handler = args.handler
    try:
        return handler(args)
    except (ConfigurationError, PaccRenderError, OSError, ValueError) as exc:
        print(f"automx: {exc}", file=sys.stderr)
        return 2
