#!/usr/bin/env bash
# Build and run the host-side tests for the offline Seeed bridge loopback.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
app="$root/firmware/seeed-nrf54l15-bridge"
outdir="$root/build/seeed-bridge-host-test"
binary="$outdir/test_seeed_bridge"

mkdir -p "$outdir"

"${CXX:-c++}" \
  -std=c++11 -Wall -Wextra -Werror \
  -I"$app/src" -I"$root/firmware/rp2040-bridge/src" \
  "$here/test_seeed_bridge.cpp" "$app/src/bridge_core.cpp" \
  -o "$binary"

"$binary"
