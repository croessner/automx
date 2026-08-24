from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("path", ["Dockerfile", "compose.yaml", ".dockerignore"])
def test_container_files_exist(path: str) -> None:
    assert (ROOT / path).is_file()


def test_runtime_image_is_non_root_and_contains_no_build_toolchain() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = dockerfile.split(" AS runtime", maxsplit=1)[1]

    assert "python:3.14.7-slim-trixie" in dockerfile
    assert "USER automx" in runtime
    assert "HEALTHCHECK" in runtime
    assert "pip install" not in runtime
    assert "build-essential" not in runtime
    assert " gcc" not in runtime
    assert "COPY . ." not in dockerfile


def test_compose_runtime_hardening_is_explicit() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose and "- ALL" in compose
    assert "tmpfs:" in compose
    assert "/etc/automx/automx.conf:ro" in compose


def test_e2e_stack_and_probe_cover_every_public_protocol_family() -> None:
    runner = (ROOT / "contrib/e2e/run.sh").read_text(encoding="utf-8")
    compose = (ROOT / "contrib/e2e/compose.yaml").read_text(encoding="utf-8")

    assert "id -u" in runner
    assert "read-only filesystem" in runner
    for contract in (
        "probe",
        "all",
        "--include-experimental",
        "--allow-insecure-http",
        "--config",
    ):
        assert contract in compose
    assert "openapi check" in runner
    assert "dns records" in runner
    assert not (ROOT / "src/automx-test").exists()
