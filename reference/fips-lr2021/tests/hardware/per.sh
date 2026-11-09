#!/usr/bin/env bash
# Same-host PER for the E80/ESP32 bridge pair.
#
# Direction A -> B by default. To test B -> A, swap SERIAL_A and SERIAL_B.
# The script starts the responder, sends a bounded burst, then reports both the
# link-layer delivery count and the bridge statistics. It never uses a US band.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
ctl="$fips/target/release/fips-lr2021ctl"

band="${BAND:-eu868}"
payload="${RADIO_PAYLOAD:-128}"
a="${SERIAL_A:-/dev/ttyACM0}"
b="${SERIAL_B:-/dev/ttyACM1}"
count="${1:-20}"
max_data=$((payload - 24)) # link header (20) + CRC32 (4)
size="${2:-$max_data}"
timeout_ms="${TIMEOUT_MS:-500}"
sync="${SYNC_WORD:-2dd4d4b2}"
direction="${DIRECTION:-A_TO_B}"
logdir="${LOG_DIR:-$(mktemp -d /tmp/fips-per.XXXXXX)}"

case "$band" in
  eu868|eu868-high|eu2400) ;;
  us*|*us*) echo "refusing non-EU band: $band" >&2; exit 2 ;;
esac

if [ ! -x "$ctl" ]; then
  echo "missing $ctl (set FIPS_DIR to the built fork)" >&2
  exit 2
fi
if [ "$size" -lt 8 ] || [ "$size" -gt "$max_data" ]; then
  echo "size $size is outside 8..$max_data for radio_payload=$payload" >&2
  exit 2
fi

echo_pid=""
cleanup() {
  if [ -n "$echo_pid" ]; then kill "$echo_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT

mkdir -p "$logdir"
echo_log="$logdir/responder-echo.log"
sender_before="$logdir/sender-status-before.log"
sender_after="$logdir/sender-status-after.log"
receiver_after="$logdir/receiver-status-after.log"

"$ctl" --serial "$b" --sync-word "$sync" echo \
  --band "$band" --radio-payload "$payload" --seconds 65 >"$echo_log" 2>&1 &
echo_pid=$!
sleep 3

"$ctl" --serial "$a" --sync-word "$sync" status >"$sender_before" 2>&1 || true
"$ctl" --serial "$a" --sync-word "$sync" per \
  --band "$band" --radio-payload "$payload" \
  --count "$count" --size "$size" --timeout-ms "$timeout_ms" --peer-id 2 \
  2>&1 | tee "$logdir/sender-per.log"

sleep 1
cleanup
echo_pid=""

"$ctl" --serial "$a" --sync-word "$sync" status >"$sender_after" 2>&1 || true
"$ctl" --serial "$b" --sync-word "$sync" status >"$receiver_after" 2>&1 || true

accepted="$(grep -c 'echo rx len=' "$echo_log" || true)"
unique="$(awk -F'data=' '/echo rx len=/{print substr($2,1,8)}' "$echo_log" | sort -u | wc -l)"
bad="$(grep -cE 'bad magic|bad crc32' "$echo_log" || true)"
per_line="$(grep -E '^per:' "$logdir/sender-per.log" | tail -1 || true)"

echo "RESULT direction=$direction band=$band payload=$payload size=$size count=$count timeout_ms=$timeout_ms"
echo "$per_line"
echo "responder_accepted=$accepted unique_payloads=$unique responder_link_errors=$bad logs=$logdir"
echo "sender_before: $(tail -1 "$sender_before")"
echo "sender_after:  $(tail -1 "$sender_after")"
echo "receiver_after: $(tail -1 "$receiver_after")"

if [ "$accepted" -ne "$count" ] || [ "$unique" -ne "$count" ]; then
  echo "FAIL: responder accepted $accepted/$count, unique payloads $unique/$count" >&2
  exit 1
fi
if [ "$bad" -ne 0 ]; then
  echo "FAIL: $bad host link CRC/framing errors" >&2
  exit 1
fi
echo "PASS: responder accepted $count/$count unique payloads"
