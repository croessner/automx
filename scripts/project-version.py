#!/usr/bin/env python3
"""Print the canonical project version from pyproject.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path


def main() -> int:
    """Write only the configured project version to stdout."""

    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    print(metadata["project"]["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
