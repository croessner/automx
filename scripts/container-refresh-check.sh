#!/usr/bin/env bash
set -euo pipefail

image=""
expected_python_digest=""

usage() {
  cat <<'USAGE'
Usage: scripts/container-refresh-check.sh [options]

Options:
  --image <image>                     Stable image tag to inspect.
  --expected-python-digest <digest>  Current Python base manifest digest.
  -h, --help                         Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)
      image="$2"
      shift 2
      ;;
    --expected-python-digest)
      expected_python_digest="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${image}" || -z "${expected_python_digest}" ]]; then
  usage >&2
  exit 1
fi

if ! docker pull "${image}" >/dev/null 2>&1; then
  echo "reason=image-missing"
  echo "should_rebuild=true"
  exit 0
fi

existing_python_digest="$(
  docker inspect \
    --format '{{ index .Config.Labels "io.automx.base.python.digest" }}' \
    "${image}" 2>/dev/null || true
)"
printf 'existing_python_digest=%s\n' "${existing_python_digest}"

if [[ -z "${existing_python_digest}" ]]; then
  echo "reason=missing-base-digest-label"
  echo "should_rebuild=true"
  exit 0
fi

if [[ "${existing_python_digest}" != "${expected_python_digest}" ]]; then
  echo "reason=python-base-digest-changed"
  echo "should_rebuild=true"
  exit 0
fi

echo "reason=up-to-date"
echo "should_rebuild=false"
