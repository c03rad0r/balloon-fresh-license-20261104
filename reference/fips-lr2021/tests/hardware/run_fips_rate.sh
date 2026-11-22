#!/usr/bin/env bash
# Focused FIPS-over-LR2021 rate test. Starts the two isolated containers, then
# runs one offered rate at a time and leaves them running for inspection.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
config_dir="${FIPS_E2E_CONFIG_DIR:-$root/build/fips-e2e}"
image="${FIPS_E2E_IMAGE:-seeed-fips-e2e:latest}"
name_a="${FIPS_E2E_NAME_A:-seeed-fips-a}"
name_b="${FIPS_E2E_NAME_B:-seeed-fips-b}"
rates="${RATES:-10k 25k 50k}"
seconds="${SECONDS_PER_RATE:-10}"
length="${IPERF_LEN:-300}"

[ -f "$config_dir/node-a.yaml" ] && [ -f "$config_dir/node-b.yaml" ] || {
    echo "missing private configs in $config_dir" >&2
    exit 1
}

docker rm -f "$name_a" "$name_b" >/dev/null 2>&1 || true

docker run -d --name "$name_a" \
    --network none --cap-add NET_ADMIN --device /dev/net/tun \
    --device /dev/ttyACM0:/dev/ttyACM0 \
    -v "$config_dir:/config:ro" \
    "$image" /usr/local/bin/fips --config /config/node-a.yaml >/dev/null
docker run -d --name "$name_b" \
    --network none --cap-add NET_ADMIN --device /dev/net/tun \
    --device /dev/ttyACM1:/dev/ttyACM1 \
    -v "$config_dir:/config:ro" \
    "$image" /usr/local/bin/fips --config /config/node-b.yaml >/dev/null

for _ in $(seq 1 30); do
    if docker exec "$name_a" fipsctl show status >/dev/null 2>&1 \
       && docker exec "$name_b" fipsctl show status >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

addr_of() {
    docker exec "$1" sh -c \
        "ip -6 addr show dev fips0 | awk '/inet6 fd/ {print \$2}' | cut -d/ -f1 | head -1"
}
addr_a=$(addr_of "$name_a")
addr_b=$(addr_of "$name_b")
printf 'A=%s B=%s\n' "$addr_a" "$addr_b"
[ -n "$addr_a" ] && [ -n "$addr_b" ] || { docker logs --tail 30 "$name_a"; docker logs --tail 30 "$name_b"; exit 1; }

for _ in $(seq 1 20); do
    if docker exec "$name_a" fipsctl show peers 2>/dev/null | grep -q '"connectivity": "connected"'; then
        break
    fi
    sleep 1
done
printf 'peer: '
docker exec "$name_a" fipsctl show peers 2>/dev/null | grep -m1 '"connectivity"' || true

printf '\nping6:\n'
timeout 30 docker exec "$name_a" ping6 -c 5 -I fips0 "$addr_b" 2>&1 | tail -3 || true

docker exec "$name_b" pkill -x iperf3 2>/dev/null || true
docker exec "$name_b" sh -c "nohup iperf3 -s -B '$addr_b' -p 5201 >/tmp/iperf3.log 2>&1 &"
sleep 1

for rate in $rates; do
    printf '\n=== UDP offered %s (%ss, %s B) ===\n' "$rate" "$seconds" "$length"
    timeout $((seconds + 20)) docker exec "$name_a" \
        iperf3 -c "$addr_b" -p 5201 -u -b "$rate" -l "$length" -t "$seconds" \
        --connect-timeout 5000 2>&1 | tail -8 || true
    sleep 2
done

docker exec "$name_b" pkill -x iperf3 2>/dev/null || true
printf '\ncontainers left running: %s %s\n' "$name_a" "$name_b"
