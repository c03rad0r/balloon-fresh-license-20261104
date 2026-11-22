#!/usr/bin/env bash
# End-to-end host test: two virtual bridges, real serial codec, link layer and CLI.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
target_dir="${CARGO_TARGET_DIR:-$fips/target}"
ctl="$target_dir/release/fips-lr2021ctl"
[ -x "$ctl" ] || ctl="$target_dir/debug/fips-lr2021ctl"
if [ ! -x "$ctl" ]; then
  "$root/scripts/build.sh"
  ctl="$target_dir/release/fips-lr2021ctl"
fi

python3 "$here/mock_radio.py" /tmp/fips-lr2021-a /tmp/fips-lr2021-b >/tmp/fips-lr2021-mock.log 2>&1 &
mock=$!
trap 'kill "$mock" 2>/dev/null || true' EXIT
sleep 1

"$ctl" --serial /tmp/fips-lr2021-a cfg --band us915 >/dev/null
"$ctl" --serial /tmp/fips-lr2021-b cfg --band us915 >/dev/null
"$ctl" --serial /tmp/fips-lr2021-b echo --band us915 --seconds 12 >/tmp/fips-lr2021-echo.log 2>&1 &
echo_pid=$!
sleep 1
out="$("$ctl" --serial /tmp/fips-lr2021-a per --band us915 --count 20 --size 64 --peer-id 2)"
echo "$out"
wait "$echo_pid" || true

if ! grep -q 'delivered=20 loss=0.0' <<<"$out"; then
  echo "mock end-to-end failed; echo log:" >&2
  cat /tmp/fips-lr2021-echo.log >&2
  exit 1
fi
echo "mock end-to-end: PASS"
