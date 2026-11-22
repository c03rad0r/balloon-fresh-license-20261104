#!/usr/bin/env bash
# Alternating-direction FLRC soak using the existing link-layer PER tool.
#
# The caller must already hold the external board lock. Every burst uses the
# same two EVKs; the direction swaps each iteration so both radios transmit.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
target_dir="${CARGO_TARGET_DIR:-$fips/target}"
ctl="${CTL:-$target_dir/release/fips-lr2021ctl}"
band="${BAND:-eu2400}"
baud="${BAUD:-1000000}"
port_a="${PORT_A:-/dev/serial/by-id/usb-Seeed_Studio_Seeed_Studio_XIAO_nrf54_CMSIS-DAP_7CDB5271-if02}"
port_b="${PORT_B:-/dev/serial/by-id/usb-Seeed_Studio_Seeed_Studio_XIAO_nrf54_CMSIS-DAP_A8022EF0-if02}"
seconds="${SOAK_SECONDS:-600}"
count="${SOAK_COUNT:-200}"
size="${SOAK_SIZE:-64}"
timeout_ms="${TIMEOUT_MS:-500}"
max_loss_pct="${MAX_LOSS_PCT:-1.0}"
log="${SOAK_LOG:-$root/build/flrc/soak.log}"

mkdir -p "$(dirname "$log")"
[ -x "$ctl" ] || "$root/scripts/build.sh"

start=$(date +%s)
iteration=0
failures=0

printf '%s soak start duration=%ss count=%s size=%s band=%s baud=%s\n' \
    "$(date -Is)" "$seconds" "$count" "$size" "$band" "$baud" | tee -a "$log"

while (( $(date +%s) - start < seconds )); do
    iteration=$((iteration + 1))
    if (( iteration % 2 == 1 )); then
        direction="B->A"
        sender="$port_b"
        responder="$port_a"
    else
        direction="A->B"
        sender="$port_a"
        responder="$port_b"
    fi

    output=$(
        FIPS_DIR="$fips" BAND="$band" BAUD="$baud" TIMEOUT_MS="$timeout_ms" \
        SERIAL_A="$sender" SERIAL_B="$responder" \
        "$here/per.sh" "$count" "$size" 2>&1
    ) || true
    summary=$(grep -E '^per:' <<<"$output" | tail -1 || true)
    if [ -z "$summary" ]; then
        printf '%s iteration=%d %s ERROR no-summary\n' "$(date -Is)" "$iteration" "$direction" | tee -a "$log"
        failures=$((failures + 1))
        continue
    fi

    loss=$(sed -n 's/.*loss=\([0-9.]*\)%.*/\1/p' <<<"$summary")
    printf '%s iteration=%d %s %s\n' "$(date -Is)" "$iteration" "$direction" "$summary" | tee -a "$log"

    if [ -n "$loss" ] && awk -v l="$loss" -v m="$max_loss_pct" 'BEGIN { exit !(l > m) }'; then
        failures=$((failures + 1))
    fi

    if (( iteration % 5 == 0 )); then
        for port in "$port_a" "$port_b"; do
            status=$("$ctl" --serial "$port" --baud "$baud" status 2>&1 | tail -1 || true)
            printf '%s status %s %s\n' "$(date -Is)" "$port" "$status" | tee -a "$log"
        done
    fi
done

printf '%s soak end iterations=%d failures=%d\n' \
    "$(date -Is)" "$iteration" "$failures" | tee -a "$log"

if (( failures > 0 )); then
    exit 1
fi
