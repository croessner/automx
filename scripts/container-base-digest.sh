#!/usr/bin/env bash
set -euo pipefail

python_image="${PYTHON_IMAGE:-python:3.14.7-slim-trixie}"

hash_cmd() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256
    return
  fi
  echo "No SHA-256 tool found (sha256sum/shasum)." >&2
  exit 1
}

manifest_digest() {
  local image="$1"
  local digest

  digest="$(
    docker buildx imagetools inspect "${image}" --raw \
      | hash_cmd \
      | awk '{print $1}'
  )"
  printf 'sha256:%s\n' "${digest}"
}

printf 'python_image=%s\n' "${python_image}"
printf 'python_digest=%s\n' "$(manifest_digest "${python_image}")"
