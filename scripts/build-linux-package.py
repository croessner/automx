#!/usr/bin/env python3
"""Build native DEB or RPM artifacts from the staged automx package root."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PACKAGE_NAME = "automx"
DESCRIPTION = "Standards-oriented automatic account configuration service"
MAINTAINER = "Christian Roessner <c@roessner.co>"
LICENSE = "GPL-3.0-or-later"
PACKAGE_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){2}(?:~[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?")
ARCHITECTURES = {"deb": frozenset({"amd64", "arm64"}), "rpm": frozenset({"x86_64"})}


def _validated_path(path: str, *, directory: bool) -> Path:
    """Resolve an existing input directory or a bounded output directory."""
    resolved = Path(path).resolve()
    if directory and not resolved.is_dir():
        raise ValueError(f"Package root is not a directory: {resolved}")
    if not directory:
        resolved.mkdir(parents=True, exist_ok=True)
        if not resolved.is_dir():
            raise ValueError(f"Output path is not a directory: {resolved}")
    return resolved


def _tool(name: str) -> str:
    """Resolve a required native packaging command without invoking a shell."""
    executable = shutil.which(name)
    if executable is None:
        raise ValueError(f"Required packaging command is unavailable: {name}")
    return executable


def _run(command: list[str]) -> None:
    """Run one bounded native packaging command with explicit arguments."""
    subprocess.run(command, check=True, timeout=600)  # noqa: S603 - resolved tool, fixed argv


def _installed_size_kib(package_root: Path) -> int:
    """Return the regular-file payload size rounded up to one KiB."""
    size = sum(
        entry.stat().st_size
        for entry in package_root.rglob("*")
        if entry.is_file() and not entry.is_symlink()
    )
    return max(1, (size + 1023) // 1024)


def _copy_package_root(source: Path, destination: Path) -> None:
    """Copy the complete staged filesystem while preserving symbolic links."""
    shutil.copytree(source, destination, symlinks=True)


def _build_deb(package_root: Path, output_dir: Path, version: str, arch: str) -> Path:
    output = output_dir / f"{PACKAGE_NAME}_{version}_{arch}.deb"
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="automx-deb-") as temporary:
        staging = Path(temporary) / PACKAGE_NAME
        _copy_package_root(package_root, staging)
        control_dir = staging / "DEBIAN"
        control_dir.mkdir(mode=0o755)
        control = (
            f"Package: {PACKAGE_NAME}\n"
            f"Version: {version}\n"
            "Section: net\n"
            "Priority: optional\n"
            f"Architecture: {arch}\n"
            f"Maintainer: {MAINTAINER}\n"
            f"Installed-Size: {_installed_size_kib(package_root)}\n"
            f"Description: {DESCRIPTION}\n"
        )
        (control_dir / "control").write_text(control, encoding="utf-8")
        _run([_tool("dpkg-deb"), "--root-owner-group", "--build", str(staging), str(output)])
    if not output.is_file():
        raise RuntimeError(f"DEB builder did not create the expected artifact: {output}")
    return output


def _rpm_spec(version: str, arch: str) -> str:
    """Return a minimal spec that copies the complete package root atomically."""
    return f"""Name: {PACKAGE_NAME}
Version: {version}
Release: 1
Summary: {DESCRIPTION}
License: {LICENSE}
BuildArch: {arch}
AutoReqProv: no

%description
{DESCRIPTION}

%prep

%build

%install
rm -rf "%{{buildroot}}"
mkdir -p "%{{buildroot}}"
cp -a "%{{_sourcedir}}/package-root/." "%{{buildroot}}/"

%files
%defattr(-,root,root,-)
/opt/automx
/usr/bin/automx
/usr/lib/systemd/system/automx.service
/usr/share/doc/automx
"""


def _build_rpm(package_root: Path, output_dir: Path, version: str, arch: str) -> Path:
    filename = f"{PACKAGE_NAME}-{version}-1.{arch}.rpm"
    output = output_dir / filename
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="automx-rpm-") as temporary:
        topdir = Path(temporary)
        sources = topdir / "SOURCES"
        specs = topdir / "SPECS"
        sources.mkdir()
        specs.mkdir()
        _copy_package_root(package_root, sources / "package-root")
        spec = specs / "automx.spec"
        spec.write_text(_rpm_spec(version, arch), encoding="utf-8")
        _run(
            [
                _tool("rpmbuild"),
                "-bb",
                "--define",
                f"_topdir {topdir}",
                "--define",
                f"_rpmdir {output_dir}",
                "--define",
                f"_rpmfilename {filename}",
                str(spec),
            ]
        )
    if not output.is_file():
        raise RuntimeError(f"RPM builder did not create the expected artifact: {output}")
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_format", choices=sorted(ARCHITECTURES))
    parser.add_argument("--package-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--arch", required=True)
    return parser


def main() -> int:
    """Validate release metadata and build exactly one native package."""
    parser = _parser()
    arguments = parser.parse_args()
    package_format = str(arguments.package_format)
    version = str(arguments.version)
    arch = str(arguments.arch)
    if PACKAGE_VERSION.fullmatch(version) is None:
        parser.error("--version must be a normalized package version")
    if arch not in ARCHITECTURES[package_format]:
        parser.error(f"--arch must be one of: {', '.join(sorted(ARCHITECTURES[package_format]))}")
    try:
        package_root = _validated_path(str(arguments.package_root), directory=True)
        output_dir = _validated_path(str(arguments.output_dir), directory=False)
        if package_format == "deb":
            output = _build_deb(package_root, output_dir, version, arch)
        else:
            output = _build_rpm(package_root, output_dir, version, arch)
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as error:
        parser.error(str(error))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
