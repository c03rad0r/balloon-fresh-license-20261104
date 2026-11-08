#!/usr/bin/env bash
# Measure HTTP transfer goodput from inside a FIPS network namespace.
#
# Prerequisites:
#   - both FIPS peers are authenticated;
#   - `show sessions` is non-empty on both;
#   - PING_IP passes 0% packet loss from this namespace.
#
# The script deliberately refuses to run when PING_IP is not set or has loss.
# Point URL at an HTTP server on the far side of the LR2021/FIPS peer. External
# URLs are allowed only when this namespace has no Wi-Fi/Ethernet fallback
# route, otherwise the result is not a bridge measurement.
set -euo pipefail

: "${NETNS:?set NETNS to the FIPS test namespace}"
: "${URL:?set URL to a small test payload served over the FIPS path}"
: "${PING_IP:?set PING_IP to the far FIPS IPv6 address for the preflight gate}"
RUNS="${RUNS:-3}"
RUNNER=(sudo -n ip netns exec "$NETNS")

echo "== preflight: IPv6 ping gate =="
ping_out="$("${RUNNER[@]}" ping -6 -c 3 -W 5 "$PING_IP" 2>&1 || true)"
printf '%s\n' "$ping_out"
if ! printf '%s\n' "$ping_out" | grep -q ' 0% packet loss'; then
  echo "REFUSED: ping gate requires 0% packet loss in $NETNS" >&2
  exit 2
fi

echo "== HTTP throughput: $URL =="
"${RUNNER[@]}" python3 - "$URL" "$RUNS" <<'PY'
import json
import sys
import time
import urllib.request

url = sys.argv[1]
runs = int(sys.argv[2])
results = []
for n in range(runs):
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=120) as response:
        first = response.read(16384)
        first_at = time.perf_counter()
        body = bytearray(first)
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            body.extend(chunk)
        finished = time.perf_counter()
        status = response.status
    elapsed = finished - started
    row = {
        "run": n + 1,
        "status": status,
        "bytes": len(body),
        "ttfb_ms": round((first_at - started) * 1000, 3),
        "total_ms": round(elapsed * 1000, 3),
        "goodput_mbps": round((len(body) * 8 / elapsed) / 1_000_000, 4),
    }
    print(json.dumps(row, sort_keys=True))
    results.append(row)
if results:
    avg = sum(r["goodput_mbps"] for r in results) / len(results)
    print(json.dumps({"runs": len(results), "mean_goodput_mbps": round(avg, 4)}, sort_keys=True))
PY
