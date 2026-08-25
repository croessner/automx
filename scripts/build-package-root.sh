#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: scripts/build-package-root.sh <standalone-dir> <package-root>" >&2
  exit 1
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
standalone_dir="$1"
package_root="$2"

if [[ ! -x "${standalone_dir}/automx" ]]; then
  echo "Standalone automx executable is missing: ${standalone_dir}/automx" >&2
  exit 1
fi
case "${package_root}" in
  ""|/|.)
    echo "Refusing unsafe package root: '${package_root}'" >&2
    exit 1
    ;;
esac

mkdir -p \
  "${package_root}/opt/automx" \
  "${package_root}/usr/bin" \
  "${package_root}/usr/lib/systemd/system" \
  "${package_root}/usr/share/doc/automx"
cp -R "${standalone_dir}/." "${package_root}/opt/automx/"
ln -sfn /opt/automx/automx "${package_root}/usr/bin/automx"
install -m 0644 \
  "${root_dir}/packaging/automx.service" \
  "${package_root}/usr/lib/systemd/system/automx.service"
install -m 0644 \
  "${root_dir}/contrib/production-example/automx.conf" \
  "${package_root}/usr/share/doc/automx/automx.conf.example"
install -m 0644 "${root_dir}/README.md" "${package_root}/usr/share/doc/automx/README.md"
install -m 0644 "${root_dir}/LICENSE" "${package_root}/usr/share/doc/automx/LICENSE"
