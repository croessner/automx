from __future__ import annotations

import pytest

from automx import __version__
from automx.mojo_entrypoint import run


@pytest.mark.parametrize(
    ("argv", "expected_status"),
    [
        (["--version"], 0),
        (["--help"], 0),
        ([], 2),
    ],
)
def test_mojo_bridge_normalizes_argparse_system_exit(
    argv: list[str], expected_status: int
) -> None:
    assert run(argv) == expected_status


def test_mojo_bridge_preserves_version_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert run(["--version"]) == 0

    assert capsys.readouterr().out == f"automx {__version__}\n"
