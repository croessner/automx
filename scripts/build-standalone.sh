#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${1:-${root_dir}/dist/standalone}"
python_bin="${PYTHON_BIN:-${root_dir}/.venv/bin/python}"
config_dir="${PYINSTALLER_CONFIG_DIR:-/tmp/automx-pyinstaller-config}"

if [[ "${python_bin}" != */* ]]; then
  python_bin="$(command -v "${python_bin}" || true)"
fi

if [[ -z "${python_bin}" || ! -x "${python_bin}" ]]; then
  echo "Python interpreter is not executable: ${python_bin}" >&2
  exit 1
fi

mkdir -p "${output_dir}" "${config_dir}" /tmp/automx-pyinstaller-build
PYINSTALLER_CONFIG_DIR="${config_dir}" "${python_bin}" -m PyInstaller \
  --clean \
  --noconfirm \
  --onedir \
  --name automx \
  --paths "${root_dir}/src" \
  --collect-submodules automx \
  --collect-submodules sqlalchemy \
  --collect-submodules ldap \
  --collect-submodules pymemcache \
  --distpath "${output_dir}" \
  --workpath /tmp/automx-pyinstaller-build \
  --specpath /tmp \
  "${root_dir}/packaging/entrypoint.py"

"${output_dir}/automx/automx" --version
