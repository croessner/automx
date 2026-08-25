#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/release-semver-metadata.sh <tag> [project-version]

Print GitHub Actions output lines for supported release tags. Supported tags
use vMAJOR.MINOR.PATCH with an optional SemVer prerelease suffix, for example
v3.0.0, v3.0.0-rc.1, or v3.0.0-beta.4. If project-version is supplied, the tag
must describe that exact version.
USAGE
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage >&2
  exit 1
fi

tag="$1"
project_version="${2:-}"
semver_pattern='^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(\.(0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?$'

if [[ ! "${tag}" =~ ${semver_pattern} ]]; then
  echo "Unsupported release tag '${tag}'. Expected vMAJOR.MINOR.PATCH[-PRERELEASE]." >&2
  exit 1
fi

version="${tag#v}"
if [[ -n "${project_version}" && "${version}" != "${project_version}" ]]; then
  echo "Release tag version '${version}' does not match project version '${project_version}'." >&2
  exit 1
fi

base_version="${version%%-*}"
base_tag="${tag%%-*}"
prerelease=false
if [[ "${version}" == *-* ]]; then
  prerelease=true
fi
IFS='.' read -r major minor patch <<< "${base_version}"

printf 'tag=%s\n' "${tag}"
printf 'version=%s\n' "${version}"
printf 'base_version=%s\n' "${base_version}"
printf 'package_version=%s\n' "${version//-/\~}"
printf 'prerelease=%s\n' "${prerelease}"
printf 'tag_major=v%s\n' "${major}"
printf 'tag_minor=v%s.%s\n' "${major}" "${minor}"
printf 'tag_patch=%s\n' "${base_tag}"
printf 'major=%s\n' "${major}"
printf 'minor=%s\n' "${minor}"
printf 'patch=%s\n' "${patch}"
