# Flashing boards with no physical access

Written 2026-11-05. **Read this before asking anyone to press a button.** Two of
the three board families can be flashed entirely over USB.

## TL;DR

| Board | Trick | Works without hands? |
|---|---|---|
| ESP32-C3 / S3 | `esptool --before usb_reset` | **yes** |
| RP2040 (Pico) | **1200-baud touch** → BOOTSEL → copy UF2 | **yes** |
| E80 STM32 | SWD only | **no** |

## RP2040: the 1200-baud touch

The PlatformIO/Arduino RP2040 core resets into BOOTSEL when the serial port is
opened **at 1200 baud** and then closed. No button, no power cycle.

```python
import serial, time
s = serial.Serial("/dev/ttyACM0", 1200)
s.dtr = False
s.rts = False
time.sleep(0.3)
s.close()
```

The Pico then re-enumerates as a mass-storage device:

```bash
line=$(lsblk -lno NAME,LABEL | awk '$2=="RPI-RP2"{print $1; exit}')
sudo mount "/dev/$line" /mnt/rp2040
sudo cp firmware.uf2 /mnt/rp2040/
sync
sudo umount /mnt/rp2040        # device reboots and runs the new image
```

Verify it came back:

```bash
ls /dev/serial/by-id | grep -i pico
```

### Details that cost time

- A **`Broken pipe` exception is expected** — the device disappears as it
  reboots. It does not mean the touch failed.
- Use `lsblk -lno`, not `-no`: the tree glyphs produce paths like `/dev/`-sdc1`.
- Poll for the `RPI-RP2` label rather than sleeping a fixed time.
- Works because the core implements the touch reset. A bare-metal image that does
  not implement it will ignore the touch.

## ESP32-C3 / S3: `usb_reset`

`esptool` can put the chip into ROM download mode over the USB-Serial/JTAG
peripheral:

```bash
esptool --chip esp32c3 -p /dev/ttyACM5 -b 460800 \
  --before usb_reset --after watchdog_reset \
  write-flash 0x0 bootloader.bin \
              0x8000 partition-table.bin \
              0x10000 app.bin
```

### Why the other reset modes fail

| Option | Result |
|---|---|
| `--before usb_reset` | **works** |
| `--before default_reset` | usually fails; no DTR/RTS is wired |
| `--after hard_reset` | prints "Hard resetting via RTS pin" but **does not reset** USB-Serial/JTAG chips |
| `--after watchdog_reset` | **required** — actually reboots into the application |

`--after watchdog_reset` needs esptool **5.x**. Ubuntu 24.04 ships 4.x:

```
esptool: error: argument --after/-a: invalid choice: 'watchdog_reset'
```

Install a current one rather than fighting the system package:

```bash
python3 -m venv /tmp/esptool-venv
/tmp/esptool-venv/bin/pip install -q esptool
```

### The exception

Firmware that claims the USB PHY for OTG (e.g. `esp-usb-bridge`, which enumerates
as `303a:1002`) **cannot** be reset this way — the USB-Serial/JTAG peripheral is
not active. Those boards need BOOT + RESET.

Practical tell: `Invalid head of packet` from `esptool --before usb_reset chip-id`
means the device is running OTG firmware or is otherwise not resettable.

## E80 STM32: no remote path

Two routes exist and both need hands on the board:

1. **SWD** via a probe on the `C D G` header — reliable, and the only route that
   has ever worked.
2. **UART ROM bootloader** (`FLASH` + `stm32flash`). The board accepts `FLASH`
   and answers `OK JUMPING TO BOOTLOADER`, but the onboard **CH340 cannot
   complete the STM32 bootloader's 8E1 handshake**:

```text
Failed to init device, timeout.
-i none       -> Failed to send boot enter sequence
-i -dtr&-rts  -> Failed to init device, timeout
-b 9600       -> Failed to init device, timeout
```

Confirmed on two different hosts, so it is the CH340, not the machine.

**Consequence:** leave a probe wired to any E80 that may need reflashing.

## Recovery without a button

`uhubctl` can power-cycle a USB port, which reboots a hung board — but it boots
the **application**, not the bootloader. It is recovery, not flashing.

```bash
sudo uhubctl                          # list hubs and ports
sudo uhubctl -l 1-1.2.1 -p 1 -a cycle # cycle one port
```

`uhubctl` is **not installed** on `archipelago.local`.

## Related

- `docs/BOARD-INVENTORY.md` — which board is which
- `docs/OTA-PROOF-PLAN.md` — radio bring-up state
- `docs/REMOTE-ACCESS-PLAN.md` — access matrix
