#!/usr/bin/env bash
# Build the patched FIPS binaries and the host tools.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"

if [ ! -d "$fips/.git" ]; then
  "$here/bootstrap-fips.sh"
fi

cd "$fips"
cargo build --release -p fips-lr2021 --bins
cargo build --release -p fips-mesh

target_dir="${CARGO_TARGET_DIR:-$fips/target}"
echo "binaries:"
ls -1 "$target_dir/release/fips" \
      "$target_dir/release/fips-lr2021d" \
      "$target_dir/release/fips-lr2021ctl" 2>/dev/null || true
