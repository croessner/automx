import tomllib
from pathlib import Path

from automx import __version__


def test_runtime_version_matches_packaging_metadata() -> None:
    root = Path(__file__).parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == metadata["project"]["version"]
