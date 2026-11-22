#!/usr/bin/env bash
# Same-host PER: B runs the link responder, A sends. For two machines, run the
# echo command on B yourself and the per command on A.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
target_dir="${CARGO_TARGET_DIR:-$fips/target}"
ctl="${CTL:-$target_dir/release/fips-lr2021ctl}"
band="${BAND:-us915}"
baud="${BAUD:-2000000}"
sync_word="${SYNC_WORD:-}"
radio_payload="${RADIO_PAYLOAD:-}"
a="${SERIAL_A:-/dev/ttyACM0}"
b="${SERIAL_B:-/dev/ttyACM1}"
count="${1:-100}"
size="${2:-64}"
timeout_ms="${TIMEOUT_MS:-1000}"

[ -x "$ctl" ] || "$root/scripts/build.sh"

sync_args=()
if [ -n "$sync_word" ]; then
  sync_args=(--sync-word "$sync_word")
fi
payload_args=()
if [ -n "$radio_payload" ]; then
  payload_args=(--radio-payload "$radio_payload")
fi

"$ctl" --serial "$b" --baud "$baud" "${sync_args[@]}" echo --band "$band" --seconds "$((count / 2 + 10))" "${payload_args[@]}" >/tmp/fips-lr2021-echo.log 2>&1 &
echo_pid=$!
trap 'kill "$echo_pid" 2>/dev/null || true' EXIT
sleep 1

"$ctl" --serial "$a" --baud "$baud" "${sync_args[@]}" cfg --band "$band" "${payload_args[@]}"
"$ctl" --serial "$a" --baud "$baud" "${sync_args[@]}" per --band "$band" --count "$count" --size "$size" --peer-id 2 --timeout-ms "$timeout_ms" "${payload_args[@]}"
kill "$echo_pid" 2>/dev/null || true
wait "$echo_pid" 2>/dev/null || true
cat /tmp/fips-lr2021-echo.log
