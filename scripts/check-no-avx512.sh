#!/bin/sh
set -eu

binary=${1:?Usage: scripts/check-no-avx512.sh <ELF-binary>}
disassembly=$(mktemp)
trap 'rm -f "$disassembly"' EXIT HUP INT TERM

objdump -d "$binary" > "$disassembly"

# AVX-512 uses the EVEX (0x62) prefix and may expose zmm or mask registers.
# Reject all three forms so an amd64 release cannot silently inherit the
# build host's AVX-512 features.
if LC_ALL=C grep -Eiq \
    '^[[:space:]]*[0-9a-f]+:[[:space:]]+62[[:space:]]|%?zmm[0-9]+|%k[0-7]' \
    "$disassembly"; then
    echo "AVX-512 instructions detected in $binary" >&2
    exit 1
fi

echo "No AVX-512 instructions detected in $binary"
