#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/release-notes.sh <to-ref> [from-ref]

Generate an English commit summary grouped by the repository's approved commit
prefixes. When from-ref is supplied, only commits in from-ref..to-ref are used.
USAGE
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage >&2
  exit 1
fi

to_ref="$1"
from_ref="${2:-}"
range="${to_ref}"
if [[ -n "${from_ref}" ]]; then
  range="${from_ref}..${to_ref}"
fi

git rev-parse --verify "${to_ref}^{commit}" >/dev/null
if [[ -n "${from_ref}" ]]; then
  git rev-parse --verify "${from_ref}^{commit}" >/dev/null
fi

printf '## Commit Summary\n\n'

section_count=0
append_section() {
  local section_title="$1"
  local grep_pattern="$2"
  local log_output

  log_output="$(
    git log "${range}" \
      --pretty=format:'- %s (%h)' \
      --no-merges \
      --extended-regexp \
      --regexp-ignore-case \
      --grep="^${grep_pattern}" || true
  )"

  if [[ -n "${log_output}" ]]; then
    printf '### %s\n%s\n\n' "${section_title}" "${log_output}"
    section_count=$((section_count + 1))
  fi
}

append_section "Added" "Add:"
append_section "Changed" "Change:"
append_section "Fixed" "Fix:"
append_section "Removed" "Remove:"
append_section "Refactored" "Refactor:"
append_section "Tests" "Test:"
append_section "Documentation" "Docs:"
append_section "Build And CI" "(Build|Ci):"
append_section "Security" "Security:"
append_section "Dependencies" "Vendor:"
append_section "Chores" "Chore:"

if [[ "${section_count}" -eq 0 ]]; then
  printf '### Other Commits\n'
  git log "${range}" --pretty=format:'- %s (%h)' --no-merges -n 20
  printf '\n'
fi
