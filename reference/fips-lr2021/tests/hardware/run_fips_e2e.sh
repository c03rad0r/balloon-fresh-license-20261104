#!/usr/bin/env bash
# Run FIPS over the two Seeed LR2021 EVKs using two isolated Docker containers.
#
# Each container gets one serial device, no general-purpose network, its own
# fips0 TUN and CAP_NET_ADMIN. All mesh traffic must therefore cross the radios.
#
# Required: CONFIG_DIR containing node-a.yaml and node-b.yaml with real nsecs
# and peer npubs. Never commit those private configs.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
config_dir="${FIPS_E2E_CONFIG_DIR:-$root/build/fips-e2e}"
serial_a="${SERIAL_A:-/dev/ttyACM0}"
serial_b="${SERIAL_B:-/dev/ttyACM1}"
image="${FIPS_E2E_IMAGE:-seeed-fips-e2e:latest}"
name_a="${FIPS_E2E_NAME_A:-seeed-fips-a}"
name_b="${FIPS_E2E_NAME_B:-seeed-fips-b}"
keep="${KEEP:-0}"

for file in "$config_dir/node-a.yaml" "$config_dir/node-b.yaml"; do
    [ -f "$file" ] || { echo "missing $file" >&2; exit 1; }
done
for dev in "$serial_a" "$serial_b"; do
    [ -c "$dev" ] || { echo "$dev is not a character device" >&2; exit 1; }
done

cleanup() {
    if [ "$keep" != 1 ]; then
        docker rm -f "$name_a" "$name_b" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

docker rm -f "$name_a" "$name_b" >/dev/null 2>&1 || true

docker run -d --name "$name_a" \
    --network none --cap-add NET_ADMIN \
    --device /dev/net/tun \
    --device "$serial_a:/dev/ttyACM0" \
    -v "$config_dir:/config:ro" \
    "$image" /usr/local/bin/fips --config /config/node-a.yaml >/dev/null

docker run -d --name "$name_b" \
    --network none --cap-add NET_ADMIN \
    --device /dev/net/tun \
    --device "$serial_b:/dev/ttyACM1" \
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
iperf_len="${IPERF_LEN:-300}"
[ -n "$addr_a" ] && [ -n "$addr_b" ] || {
    echo "fips0 address missing; container logs follow" >&2
    docker logs --tail 40 "$name_a" >&2 || true
    docker logs --tail 40 "$name_b" >&2 || true
    exit 1
}

printf 'node A fips0=%s\nnode B fips0=%s\n' "$addr_a" "$addr_b"
printf '\n=== transports (A) ===\n'
docker exec "$name_a" fipsctl show transports 2>&1 || true
printf '\n=== peers (A) ===\n'
docker exec "$name_a" fipsctl show peers 2>&1 || true

for _ in $(seq 1 30); do
    if docker exec "$name_a" fipsctl show peers 2>/dev/null | grep -q 'npub'; then
        break
    fi
    sleep 1
done

printf '\n=== ping6 over fips0 ===\n'
timeout 30 docker exec "$name_a" ping6 -c 10 -I fips0 "$addr_b"

printf '\n=== iperf3 UDP ===\n'
docker exec "$name_b" pkill -x iperf3 2>/dev/null || true
docker exec "$name_b" sh -c "nohup iperf3 -s -B '$addr_b' -p 5201 >/tmp/iperf3.log 2>&1 &"
sleep 1
for rate in ${IPERF_RATES:-10k 25k 50k}; do
    printf '\n--- UDP offered %s ---\n' "$rate"
    timeout "${IPERF_TIMEOUT:-40}" docker exec "$name_a" \
        iperf3 -c "$addr_b" -p 5201 -u -b "$rate" -l "$iperf_len" \
        -t "${IPERF_SECONDS:-10}" --connect-timeout 5000 || true
done
docker exec "$name_b" pkill -x iperf3 2>/dev/null || true

printf '\n=== iperf3 TCP (bulk; may not pass) ===\n'
docker exec "$name_b" sh -c "nohup iperf3 -s -B '$addr_b' -p 5201 >/tmp/iperf3.log 2>&1 &"
sleep 1
timeout 45 docker exec "$name_a" iperf3 -c "$addr_b" -p 5201 -t 10 --connect-timeout 5000 || true
docker exec "$name_b" pkill -x iperf3 2>/dev/null || true

if [ "${RUN_SSH:-0}" = 1 ]; then
    key="${SSH_KEY:-$config_dir/id_ed25519}"
    [ -f "$key" ] && [ -f "$key.pub" ] || {
        echo "SSH key $key(.pub) missing" >&2
        exit 1
    }
    docker exec "$name_b" mkdir -p /run/sshd /root/.ssh
    docker cp "$key.pub" "$name_b:/root/.ssh/authorized_keys"
    docker exec "$name_b" chown -R root:root /root/.ssh
    docker exec "$name_b" chmod 700 /root/.ssh
    docker exec "$name_b" chmod 600 /root/.ssh/authorized_keys
    docker exec "$name_b" ssh-keygen -A >/dev/null 2>&1 || true
    docker exec -d "$name_b" /usr/sbin/sshd -D -p 2222 \
        -o "ListenAddress=$addr_b" \
        -o PermitRootLogin=prohibit-password \
        -o PasswordAuthentication=no
    docker exec "$name_a" mkdir -p /root/.ssh
    docker cp "$key" "$name_a:/root/.ssh/id_ed25519"
    docker exec "$name_a" chown -R root:root /root/.ssh
    docker exec "$name_a" chmod 600 /root/.ssh/id_ed25519
    printf '\n=== SSH over fips0 ===\n'
    timeout 20 docker exec "$name_a" ssh -i /root/.ssh/id_ed25519 -p 2222 \
        -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "root@$addr_b" 'echo SSH_OVER_FIPS_OK'
fi

if [ "$keep" = 1 ]; then
    printf '\ncontainers left running: %s %s\n' "$name_a" "$name_b"
fi
