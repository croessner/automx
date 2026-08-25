from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def _run(*args: str, cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - tests pass explicit local argv only
        args,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _outputs(stdout: str) -> dict[str, str]:
    return dict(line.split("=", maxsplit=1) for line in stdout.splitlines())


def test_release_metadata_accepts_stable_and_prerelease_tags() -> None:
    script = ROOT / "scripts/release-semver-metadata.sh"

    stable = _run(str(script), "v3.2.1")
    prerelease = _run(str(script), "v3.2.1-beta.4", "3.2.1-beta.4")

    assert stable.returncode == 0, stable.stderr
    assert {
        "version": "3.2.1",
        "package_version": "3.2.1",
        "prerelease": "false",
        "tag_major": "v3",
        "tag_minor": "v3.2",
    }.items() <= _outputs(stable.stdout).items()
    assert prerelease.returncode == 0, prerelease.stderr
    assert {
        "version": "3.2.1-beta.4",
        "package_version": "3.2.1~beta.4",
        "prerelease": "true",
    }.items() <= _outputs(prerelease.stdout).items()


@pytest.mark.parametrize("tag", ["3.2.1", "v3.2", "v3.02.1", "v3.2.1_beta1"])
def test_release_metadata_rejects_non_semver_tags(tag: str) -> None:
    completed = _run(str(ROOT / "scripts/release-semver-metadata.sh"), tag)

    assert completed.returncode != 0
    assert "Expected vMAJOR.MINOR.PATCH[-PRERELEASE]" in completed.stderr


def test_release_metadata_rejects_project_version_drift() -> None:
    completed = _run(
        str(ROOT / "scripts/release-semver-metadata.sh"),
        "v3.2.1",
        "3.2.0",
    )

    assert completed.returncode != 0
    assert "does not match project version" in completed.stderr


def test_release_notes_group_approved_commit_prefixes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ("git", "init", "-q"),
        ("git", "config", "user.name", "Automx Test"),
        ("git", "config", "user.email", "automx@example.test"),
    ):
        assert _run(*args, cwd=repo).returncode == 0
    marker = repo / "marker"
    marker.write_text("base\n", encoding="utf-8")
    assert _run("git", "add", "marker", cwd=repo).returncode == 0
    assert _run("git", "commit", "-qm", "Chore: Establish baseline", cwd=repo).returncode == 0
    base = _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
    marker.write_text("feature\n", encoding="utf-8")
    assert _run("git", "commit", "-qam", "Add: Publish release assets", cwd=repo).returncode == 0
    marker.write_text("docs\n", encoding="utf-8")
    assert _run("git", "commit", "-qam", "Docs: Explain package activation", cwd=repo).returncode == 0

    completed = _run(
        str(ROOT / "scripts/release-notes.sh"),
        "HEAD",
        base,
        cwd=repo,
    )

    assert completed.returncode == 0, completed.stderr
    assert "## Commit Summary" in completed.stdout
    assert "### Added" in completed.stdout
    assert "- Add: Publish release assets" in completed.stdout
    assert "### Documentation" in completed.stdout
    assert "- Docs: Explain package activation" in completed.stdout
    assert "Establish baseline" not in completed.stdout


def test_base_digest_hashes_the_exact_upstream_manifest(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    manifest = '{"schemaVersion":2}\n'
    docker.write_text(
        "#!/bin/sh\nprintf '{\"schemaVersion\":2}\\n'\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ | {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "PYTHON_IMAGE": "python:3.14.7-slim-trixie",
    }

    completed = _run(str(ROOT / "scripts/container-base-digest.sh"), env=env)

    assert completed.returncode == 0, completed.stderr
    assert _outputs(completed.stdout) == {
        "python_image": "python:3.14.7-slim-trixie",
        "python_digest": f"sha256:{hashlib.sha256(manifest.encode()).hexdigest()}",
    }


def test_refresh_check_rebuilds_only_for_changed_or_missing_labels(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = pull ]; then exit 0; fi\n"
        "if [ \"$1\" = inspect ]; then printf '%s\\n' \"${FAKE_BASE_DIGEST:-}\"; fi\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    base_env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    script = str(ROOT / "scripts/container-refresh-check.sh")

    current = _run(
        script,
        "--image",
        "ghcr.io/croessner/automx:v3.0.0",
        "--expected-python-digest",
        "sha256:current",
        env=base_env | {"FAKE_BASE_DIGEST": "sha256:current"},
    )
    stale = _run(
        script,
        "--image",
        "ghcr.io/croessner/automx:v3.0.0",
        "--expected-python-digest",
        "sha256:current",
        env=base_env | {"FAKE_BASE_DIGEST": "sha256:old"},
    )

    assert {"reason": "up-to-date", "should_rebuild": "false"}.items() <= _outputs(
        current.stdout
    ).items()
    assert {
        "reason": "python-base-digest-changed",
        "should_rebuild": "true",
    }.items() <= _outputs(stale.stdout).items()


def test_package_root_contains_standalone_runtime_and_hardened_unit(tmp_path: Path) -> None:
    standalone = tmp_path / "standalone"
    standalone.mkdir()
    binary = standalone / "automx"
    binary.write_text("synthetic executable\n", encoding="utf-8")
    binary.chmod(0o755)
    package_root = tmp_path / "package-root"

    completed = _run(
        str(ROOT / "scripts/build-package-root.sh"),
        str(standalone),
        str(package_root),
    )

    assert completed.returncode == 0, completed.stderr
    assert (package_root / "opt/automx/automx").is_file()
    assert (package_root / "usr/bin/automx").is_symlink()
    assert os.readlink(package_root / "usr/bin/automx") == "/opt/automx/automx"
    unit = (package_root / "usr/lib/systemd/system/automx.service").read_text(encoding="utf-8")
    assert "DynamicUser=yes" in unit
    assert "NoNewPrivileges=yes" in unit
    assert "ProtectSystem=strict" in unit
    assert "ConditionPathExists=/etc/automx/automx.conf" in unit
    assert "LoadCredential=automx.conf:/etc/automx/automx.conf" in unit
    assert "ExecStart=/opt/automx/automx serve" in unit
    assert (package_root / "usr/share/doc/automx/automx.conf.example").is_file()


def test_standalone_builder_resolves_python_from_path(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    output_dir = tmp_path / "standalone"
    bin_dir.mkdir()
    fake_python = bin_dir / "python"
    fake_python.write_text(
        "#!/bin/sh\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = --distpath ]; then\n"
        "    shift\n"
        "    mkdir -p \"$1/automx\"\n"
        "    printf '#!/bin/sh\\nexit 0\\n' >\"$1/automx/automx\"\n"
        "    chmod +x \"$1/automx/automx\"\n"
        "    exit 0\n"
        "  fi\n"
        "  shift\n"
        "done\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    env = os.environ | {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "PYTHON_BIN": "python",
        "PYINSTALLER_CONFIG_DIR": str(tmp_path / "pyinstaller-config"),
    }

    completed = _run(
        str(ROOT / "scripts/build-standalone.sh"),
        str(output_dir),
        env=env,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_dir / "automx/automx").is_file()


def test_github_workflows_cover_ci_release_containers_and_packages() -> None:
    workflows = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted((ROOT / ".github/workflows").glob("*.yml"))
    }

    assert set(workflows) == {
        "ci.yml",
        "containers.yml",
        "dev-containers.yml",
        "release.yml",
    }
    assert "features" in workflows["ci.yml"] and "main" in workflows["ci.yml"]
    for gate in ("make check", "make coverage", "make audit", "make dist"):
        assert gate in workflows["release.yml"]
    assert "Dockerfile-mojo" in workflows["containers.yml"]
    assert "image: automx-mojo" in workflows["containers.yml"]
    assert "ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}" in workflows[
        "containers.yml"
    ]
    assert "docker logout ghcr.io" in workflows["containers.yml"]
    assert "container-refresh-check.sh" in workflows["containers.yml"]
    assert "build-deb-action" in workflows["release.yml"]
    assert "build-rpm-action" in workflows["release.yml"]
    assert "--generate-notes" in workflows["release.yml"]
    assert "attest-build-provenance" in workflows["release.yml"]
    assert "features" in workflows["dev-containers.yml"]
    assert ":dev" in workflows["dev-containers.yml"]
    assert "docker logout ghcr.io" in workflows["dev-containers.yml"]
    assert "run: make bootstrap" in workflows["ci.yml"]
    assert "run: make bootstrap" in workflows["release.yml"]
    assert "python -m pip install -e '.[dev]'" not in workflows["ci.yml"]
    assert "python -m pip install -e '.[dev]'" not in workflows["release.yml"]
    assert "cache: false" in workflows["ci.yml"]
    assert "cache: false" in workflows["release.yml"]


def test_e2e_waits_on_the_composite_automx_healthcheck_only() -> None:
    runner = (ROOT / "contrib/e2e/run.sh").read_text(encoding="utf-8")

    assert '--build --detach automx\n' in runner
    assert '--wait' not in runner
    assert "docker inspect --format '{{.State.Health.Status}}'" in runner
    assert 'if [ "$health_status" = "healthy" ]' in runner
    assert 'if [ "$health_attempt" -ge 30 ]' in runner


def test_external_actions_are_pinned_to_commit_shas() -> None:
    for workflow in sorted((ROOT / ".github/workflows").glob("*.yml")):
        for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            match = re.search(r"\buses:\s*([^\s]+)", line)
            if match is None or match.group(1).startswith("./"):
                continue
            reference = match.group(1).rsplit("@", maxsplit=1)[-1]
            assert re.fullmatch(r"[0-9a-f]{40}", reference), (
                f"{workflow}:{line_number} action is not commit-SHA pinned"
            )


def test_makefile_exposes_release_and_dual_image_gates() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    for target in (
        "dist:",
        "workflow-check:",
        "standalone:",
        "package-root:",
        "docker-build:",
        "docker-build-mojo:",
        "scan:",
        "scan-mojo:",
        "release-guardrails:",
    ):
        assert target in makefile
    assert "scripts/project-version.py" in makefile


def test_release_configuration_and_dependabot_match_branch_model() -> None:
    release = (ROOT / ".github/release.yml").read_text(encoding="utf-8")
    dependabot = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")

    for title in ("Breaking Changes", "Features", "Fixes", "Security", "Documentation"):
        assert title in release
    for ecosystem in ("pip", "github-actions", "docker"):
        assert f'package-ecosystem: "{ecosystem}"' in dependabot
    assert dependabot.count('target-branch: "features"') == 3
