# Remote access plan — one week without physical access

Written 2026-11-04. Constraint: no hands-on access to the hermes fleet for about
a week. Records what can still be done remotely, what cannot, and the actions
worth taking before that window starts.

## The rule that governs everything

| MCU | Flash entry | Physical button required? |
|---|---|---|
| ESP32-C3 / S3 | ROM download mode | **No** — proved: `esptool --before usb_reset` enters download mode over USB-Serial/JTAG. Exception: firmware that takes over the USB PHY (e.g. `esp-usb-bridge` on USB-OTG) cannot be reset this way |
| RP2040 | BOOTSEL mass storage | **Yes**, unless the firmware implements the 1200-baud touch reset |
| STM32 (E80) | SWD via probe, or UART ROM bootloader | **No**, *if* a probe is already wired to the debug header |

`uhubctl` can power-cycle a USB port remotely, so a hung board can be recovered.

**Proved on 2026-11-04:** an ESP32-C3 running firmware whose console is on
USB-Serial/JTAG can be put into ROM download mode over the wire with
`esptool --before usb_reset`. No button is required. The exception is firmware
that claims the USB PHY for OTG (e.g. `esp-usb-bridge`), which cannot be reset
this way — that is why the probe firmware still needed a button.

## Board status at the start of the window

| Board | Flashed | Remotely flashable | Usable |
|---|---|---|---|
| E80 A (STM32, `f89eca4`) | yes, verified | only if the probe is wired | **yes** |
| E80 B (STM32, `5fa7912`) | no `BRIDGE` command | only if the probe is wired | **no** |
| RP2040 carrier | yes, TX works | probably not | **yes** |
| ESP32-C3 + NiceRF (`B0:A6:…`) | bridge flashed | **yes** via `usb_reset` | radio untested |
| ESP32 + NiceRF (`88:56:…`) | bridge flashed | **yes** via `usb_reset` | radio untested |
| ESP32-S3 + E80 SPI (`123456`) | no | **no** — does not answer `usb_reset` | **no** |

Without a button press: **2 usable, 4 not** — and the four are exactly the boards
the new ESP-IDF bridge was written for.

## Actions before access ends

- [ ] Flash **ESP32-C3 + NiceRF** (`B0:A6:04:00:96:DC`)
- [ ] Flash **ESP32 + NiceRF** (`88:56:A6:7B:C6:98`)
- [ ] Flash **ESP32-S3 + E80** (`123456`)
- [ ] Verify each with `fips-lr2021ctl hello` → `HELLO_ACK`
- [ ] Wire the **Pico debugprobe to E80 B's debug header** and leave it connected
- [ ] Flash E80 B through that probe
- [ ] Confirm x280 survives a week: power, network, no unattended reboots
- [ ] Leave every board powered and plugged in

## What stays possible remotely

| Capability | Mechanism |
|---|---|
| Talk to any flashed bridge | `fips-lr2021ctl` over USB serial |
| Diagnose radio behaviour | `hello`, `cfg`, `status`, `monitor`, `per`, `echo` |
| Recover a hung board | `uhubctl -a cycle` on its hub port |
| Reflash an E80 | `openocd` over a wired SWD probe |
| Change host software | rebuild and re-copy binaries |

## What becomes impossible

- Any firmware change on an ESP32 board.
- Any firmware change on the RP2040 carrier.
- Recovering a board that gets physically disconnected or switched off.
- Fixing a runtime bug in the ESP-IDF bridge — which has never executed on
  hardware, so this is a live risk.
- Re-seating a loose wire, the single most common cause of "dead board" here.

## Contingency if the ESP32 bridge misbehaves

Defaults are already EU-compliant (868.1 MHz, FLRC-650, +14 dBm, sync
`2DD4D4B2`). The knobs most likely to need changing are compile-time:

| Variable | Values | Meaning |
|---|---|---|
| `E80_BRIDGE_CARRIER_INIT` | 0/1 | E80 demo init vs carrier init |
| `E80_RADIO_IRQ_DIO` | 8/9 | IRQ DIO routing |
| `E80_RFREQ_FRF` | 0/1 | frequency encoding |

Without physical access these cannot be changed on the ESP32 boards. That is the
main reason to flash all three while buttons are reachable.

## Longer-term fix

Wire an **auto-reset circuit** (DTR/RTS to EN/IO0) on the ESP32 carriers, or use a
board with a USB-UART bridge that exposes it — then flashing needs no button and
this constraint disappears. Same for the RP2040: firmware with the 1200-baud touch
reset makes BOOTSEL unnecessary.

## Access matrix (measured 2026-11-04)

### Fully automatic — flash and control, no physical access

| Board | Identifier | Evidence |
|---|---|---|
| ESP32-C3 + NiceRF | `B0:A6:04:00:96:DC` | `usb_reset` → C3 detected |
| ESP32 + NiceRF | `88:56:A6:7B:C6:98` | `usb_reset` → C3 detected, flashed twice |
| ESP32 (GPS carrier) | `70:AF:09:21:FB:18` | `usb_reset` → C3 detected |

`esptool --chip auto -p <port> --before usb_reset chip-id` is the test. If it
returns a chip type, the board can be reflashed remotely.

### Control only — no flashing

| Board | Status |
|---|---|
| E80 A (STM32, `f89eca4`) | working bridge; reconfigurable and testable over USB, but a firmware change needs the SWD probe |
| RP2040 carrier | bridge running, TX works; reflashing needs BOOTSEL, or the 1200-baud touch if the core supports it |

### Physical access required

| Board | Why |
|---|---|
| `123456` | does not answer `usb_reset`; firmware appears to own the USB PHY |
| E80 B (`5fa7912`) | no `BRIDGE` command, no probe wired → cannot be flashed |
| RP2040 carrier | only if the 1200-baud touch does not work |

### Consequence

The week is not blocked on button presses — it is blocked on the radio. The
ESP32 firmware can be iterated remotely for as long as needed, and the outstanding
`chip=0x0000` problem (radio not answering SPI) is a code/configuration issue, not
an access issue.

### Two tests worth doing while access exists

1. **RP2040 1200-baud touch** — if supported, the Pico becomes remotely flashable
   and no board needs a button again.
2. **Wire the Pico probe to E80 B permanently** — SWD is the only route to that
   board, so one probe converts a stuck board into a remotely-flashable one.
