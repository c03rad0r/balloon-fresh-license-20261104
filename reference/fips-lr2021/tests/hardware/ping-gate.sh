#!/usr/bin/env bash
# Strict bidirectional IPv6 ping gate for the FIPS LR2021 radio link.
#
# This must pass before measuring HTTP, SSH or ContextVM/MCP Internet speed.
# Both directions are tested; a one-way success is a failure.
set -euo pipefail

: "${NETNS_A:?set NETNS_A}"
: "${NETNS_B:?set NETNS_B}"
: "${IP_A:?set IP_A (namespace A FIPS IPv6)}"
: "${IP_B:?set IP_B (namespace B FIPS IPv6)}"
COUNT="${COUNT:-50}"
INTERVAL="${INTERVAL:-2}"
WINDOW_TIMEOUT="${WINDOW_TIMEOUT:-5}"
REKEY_WAIT="${REKEY_WAIT:-0}"
LOG_DIR="${LOG_DIR:-$(mktemp -d /tmp/fips-ping-gate.XXXXXX)}"
mkdir -p "$LOG_DIR"

run_direction() {
  local from_ns="$1" from_ip="$2" to_ip="$3" label="$4"
  local log="$LOG_DIR/$label.log"
  echo "== $label: $from_ip -> $to_ip ($COUNT packets, ${INTERVAL}s interval) =="
  sudo -n ip netns exec "$from_ns" ping -6 -c "$COUNT" -i "$INTERVAL" -W "$WINDOW_TIMEOUT" "$to_ip" >"$log" 2>&1 || true
  cat "$log"
  local loss
  loss="$(sed -n 's/.* \([0-9][0-9]*\)% packet loss.*/\1/p' "$log" | tail -1)"
  if [ "${loss:-100}" != "0" ]; then
    echo "FAIL: $label loss=${loss:-unknown}% (require 0%)" >&2
    return 1
  fi
  echo "PASS: $label 0% loss"
}

run_round() {
  local round="$1"
  echo "-- round $round --"
  run_direction "$NETNS_A" "$IP_A" "$IP_B" "round${round}-A-to-B"
  run_direction "$NETNS_B" "$IP_B" "$IP_A" "round${round}-B-to-A"
}

run_round 1
if [ "$REKEY_WAIT" -gt 0 ]; then
  echo "== waiting ${REKEY_WAIT}s for a session/rekey cycle =="
  sleep "$REKEY_WAIT"
  run_round 2
fi
echo "PING GATE PASS: logs=$LOG_DIR"
