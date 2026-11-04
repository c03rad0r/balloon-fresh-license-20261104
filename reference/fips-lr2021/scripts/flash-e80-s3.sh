#!/usr/bin/env bash
# Flash an E80 through an ESP32-S3 running Espressif's esp-usb-bridge in
# CMSIS-DAP SWD mode.
#
# Requirements that are easy to get wrong:
#   - a CURRENT OpenOCD (git master). Ubuntu 24.04's 0.12.0 release does not
#     connect to this bridge.
#   - adapter speed 5000. Every attempt at 100 kHz or below failed.
#
# The S3 must already be running the probe firmware and enumerate as
# 303a:1002. See docs/FLASHING-ESP32-S3.md.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
repo="$(cd "$root/../.." && pwd)"

elf="${ELF:-$repo/firmware/e80-stm32-bench/build-fw/e80_bench}"
speed="${SPEED:-5000}"

if [ ! -f "$elf" ]; then
  "$here/build-e80-bridge.sh"
fi

if ! command -v openocd >/dev/null 2>&1; then
  echo "openocd not found" >&2
  exit 1
fi

echo "== programming $(basename "$elf") at ${speed} kHz"
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed $speed; reset_config none separate; init; program $elf verify reset exit"

cat <<'EOF'

== next
The board reboots into the bench console. Enter bridge mode once per reset:

  fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 bridge
  fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 hello
  fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 cfg --band us915
EOF
