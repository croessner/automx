"""Normalize Python CLI termination for the native Mojo entrypoint."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from automx import cli


def run(argv: Sequence[str]) -> int:
    """Run the shared CLI and convert argparse's ``SystemExit`` to a status."""

    try:
        return cli.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code, file=sys.stderr)
        return 1
