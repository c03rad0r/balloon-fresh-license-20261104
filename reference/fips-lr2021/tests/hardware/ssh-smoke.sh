#!/usr/bin/env bash
# Prove one public-key SSH command over the isolated FIPS LR2021 path.
# Run on the bench host after ping-gate.sh has passed in both directions.
set -euo pipefail

: "${NETNS_A:=fips-lr-a}"
: "${NETNS_B:=fips-lr-b}"
: "${IP_A:?set IP_A to the FIPS IPv6 address in namespace A}"
SSH_PORT="${SSH_PORT:-2222}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-90}"
SSH_USER="${SSH_USER:-$(id -un)}"
HOME_DIR="$(getent passwd "$SSH_USER" | cut -d: -f6)"
if [ -z "$HOME_DIR" ] || [ ! -d "$HOME_DIR/.ssh" ]; then
  echo "missing protected $SSH_USER .ssh directory" >&2
  exit 2
fi
if [ ! -r /etc/ssh/ssh_host_ed25519_key ]; then
  sudo -n test -r /etc/ssh/ssh_host_ed25519_key || {
    echo "missing readable SSH host key" >&2
    exit 2
  }
fi

KEY="$HOME_DIR/.ssh/fips-radio-ssh-client"
CFG="$HOME_DIR/.ssh/fips-radio-sshd-config"
LOG_DIR="${LOG_DIR:-$(mktemp -d /tmp/fips-radio-ssh.XXXXXX)}"
mkdir -p "$LOG_DIR"
sshd_job=""

cleanup() {
  if [ -n "$sshd_job" ]; then kill "$sshd_job" 2>/dev/null || true; fi
  sudo -n pkill -f "^/usr/sbin/sshd -D -e -f $CFG$" 2>/dev/null || true
  rm -f "$KEY" "$KEY.pub" "$CFG"
}
trap cleanup EXIT

rm -f "$KEY" "$KEY.pub" "$CFG"
ssh-keygen -q -t ed25519 -N "" -f "$KEY"
printf '%s\n' \
  "Port $SSH_PORT" \
  "AddressFamily inet6" \
  "ListenAddress $IP_A" \
  "HostKey /etc/ssh/ssh_host_ed25519_key" \
  "AuthorizedKeysFile .ssh/fips-radio-ssh-client.pub" \
  "PasswordAuthentication no" \
  "KbdInteractiveAuthentication no" \
  "UsePAM no" \
  "AllowUsers $SSH_USER" \
  "LogLevel VERBOSE" > "$CFG"
chown "$SSH_USER:" "$KEY" "$KEY.pub" "$CFG"
chmod 600 "$KEY" "$KEY.pub" "$CFG"
sudo -n /usr/sbin/sshd -t -f "$CFG"

sudo -n ip netns exec "$NETNS_A" \
  /usr/sbin/sshd -D -e -f "$CFG" >"$LOG_DIR/sshd.log" 2>&1 &
sshd_job=$!
sleep 2

set +e
sudo -n ip netns exec "$NETNS_B" \
  ssh -F /dev/null -i "$KEY" \
    -o IdentitiesOnly=yes \
    -o BatchMode=yes \
    -o ConnectTimeout="$CONNECT_TIMEOUT" \
    -o ConnectionAttempts=1 \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile="$LOG_DIR/known_hosts" \
    -o LogLevel=VERBOSE \
    -p "$SSH_PORT" "$SSH_USER@$IP_A" \
    'echo RADIO_SSH_OK; hostname; whoami' \
    >"$LOG_DIR/client.out" 2>"$LOG_DIR/client.log"
rc=$?
set -e
cat "$LOG_DIR/client.out"
if [ "$rc" -ne 0 ] || ! grep -q '^RADIO_SSH_OK$' "$LOG_DIR/client.out"; then
  echo "FAIL: SSH rc=$rc; see $LOG_DIR/client.log and $LOG_DIR/sshd.log" >&2
  tail -20 "$LOG_DIR/client.log" >&2
  tail -20 "$LOG_DIR/sshd.log" >&2
  exit 1
fi
echo "PASS: RADIO_SSH_OK via $NETNS_B -> $NETNS_A ($IP_A), logs=$LOG_DIR"
