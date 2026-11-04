# Bring-up findings — 2026-11-03

Consolidated record of the ESP32-S3 probe work, the board diagnosis, and what is
still usable. Written so the next session does not repeat any of it.

## Headline

The ESP32-S3 running Espressif's `esp-usb-bridge` is a working CMSIS-DAP probe
for the E80, and it successfully programmed one board end to end. Two settings
had to be right, and both were wrong for most of the session:

1. **OpenOCD must be current.** Ubuntu 24.04 ships `0.12.0-1build2`, which does
   not connect to this bridge. Git master `0.12.0+dev-g8443233` does.
2. **`adapter speed 5000`.** Every failing attempt used 100 kHz or lower. 5 MHz
   is the documented speed and the only one that connects.

The Pico works at 100 kHz because it is a different CMSIS-DAP implementation.
Carrying that speed across made a healthy probe look broken.

## Verified working invocation

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 5000; reset_config none separate; init; \
      program e80_bench verify reset exit"
```

Helper: `scripts/flash-e80-s3.sh`.

## Wiring

| E80 | Signal | ESP32-S3 |
|---|---|---|
| C | SWCLK | GPIO10 |
| D | SWDIO | GPIO8 |
| G | GND | GND |
| V | 3V3 | leave open |

Confirmed by measurement, not by assumption — see the two tests below.

## Diagnostic tests worth keeping

### Output-path test

Flash firmware that drives one pin as a 2 s square wave, measure the E80 pad.
Proves the probe drives, the joint is sound, and the pad is the expected one.

### Input-path test (the one that matters for SWD)

SWD needs the probe to read the target's ACK, not just drive. A square-wave test
does not exercise the input path at all.

```c
/* GPIO8 input with pull-up; GPIO10 mirrors it */
gpio_set_level(10, gpio_get_level(8));
```

Ground pad `D`, watch pad `C`. `C` following `D` proves the input path.

Measured on S3 `94A9902E9484`: one clean falling edge, one clean rising edge.

### Board-side checks

| Measure (E80 G as reference) | Healthy | Meaning if wrong |
|---|---|---|
| `V` | ~3.3 V | rail down |
| `D`, nothing driving | ~3.3 V | STM32 not executing |
| reset button, not pressed | 3.3 V on one side | NRST shorted |

The power LED is **not** evidence of the 3.3 V rail; on these boards it often
hangs off USB 5 V.

## Symptom → cause table

| Symptom | Most likely cause |
|---|---|
| `cannot read IDR`, probe enumerates | old OpenOCD, or wrong speed |
| `CMSIS-DAP command CMD_INFO failed` | probe firmware wedged; reflash it |
| Probe drives pads but never reads | input path damaged, or board MCU dead |
| Silent UART **and** no SWD, rail and reset fine | MCU not executing |
| `303a:1001` with no stub response | application running, not download mode |
| Flash succeeds but `verify` fails | wiring or supply, not the probe |

## Firmware-state trap (cost one invalid result)

The running application and the ROM bootloader both enumerate as `303a:1001`. A
test image left on the S3 therefore produces the same "no connection" output as
a dead target. **Always confirm the probe firmware is running before trusting a
negative SWD result.**

Also: `esptool --after hard-reset` prints "Hard resetting via RTS pin" but does
not reset a chip on USB-Serial/JTAG. Use `--after watchdog-reset`.

And: do **not** power-cycle the S3. It wedged the CMSIS-DAP firmware twice; only
a reflash recovered it.

## Board inventory after this session

| Board | State |
|---|---|
| E80 A | bridge firmware flashed, responded `hello`/`cfg`/`status` |
| E80 B | MCU alive (UART works), wiring verified, SWD still fails at 5000 kHz — see below |
| E80 C (this one) | **STM32 debug port dead** — see below |

### E80 B evidence

- MCU **alive**: `ID E80BENCH v1.2 fw=5fa7912` at 115200, and it parses commands
  (`BRIDGE` returns `ERR UNKNOWN`, so that build predates bridge mode).
- S3 wiring verified **on this board**: GPIO10 -> C toggles at 2 s, and D sits at
  3.3 V, which is the target's SWDIO pull-up.
- SWD fails at 5000 kHz with the CMSIS-DAP probe confirmed present.
- **Not yet tried: lower adapter speeds on this board.** Only 5000 kHz was
  attempted here; 2000/1000/500/100 were only tried on E80 C. Given that the
  probe, the mapping and the live MCU are all verified, a marginal 5 MHz link
  over dupont wires is the most plausible remaining cause and the cheapest thing
  left to test.

### E80 C evidence

- Probe firmware confirmed present (`CMSIS-DAP: Interface ready`, FW 2.1.2).
- Probe drive verified: GPIO10 -> C, GPIO8 -> D both toggle at 2 s.
- Probe read verified: grounding D produced `MIRROR GPIO8=0` then `=1`.
- Board rail `V` = 3.3 V.
- NRST normal: 3.3 V, pulled to 0 V only while the button is pressed.
- SWD fails at 5000, 2000, 1000, 500, 100, 50 kHz.
- 120 reset-window connect attempts, probe confirmed present, no `DPIDR`.
- UART silent at 9600..921600 baud.

Conclusion: the STM32 is not executing. The board is not usable as a FIPS bridge
node.

## What E80 C is still good for

The dead part is the **STM32**. Everything else on the board is untouched:

- **The LR2021 radio module, its PA, matching and SMA paths.** This is the
  expensive part and it is independent of the MCU.
- **Power supply, USB-C, CH340, LEDs, headers.**

That makes it a legitimate **SPI-bypass radio node**. The project's own bypass
procedure already runs the radio from an external host with the STM32 held in
reset (`docs/e80-900mbl-02-eval/E80-SPI-BYPASS-WIRING.md`). A dead STM32 is not
in the way of that mode — it is in the way of the *bridge* mode, which needs the
STM32 to be alive.

Practical uses:

1. **RP2040/ESP32-S3 radio host** — drive the LR2021 directly over J2 SPI. Useful
   for FLRC range and PER measurements.
2. **Spare antenna / SMA / module donor** if another board is damaged.
3. **2.4 GHz or sub-GHz RX target** with an external host.

It cannot be used as: a USB-attached FIPS bridge (needs the STM32), or as a
self-contained node.

Reviving it would need a reflow or an MCU replacement; that is a rework job, not
a firmware job.

## Reproduce

```bash
# probe health
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 5000; reset_config none separate; init; shutdown"

# flash once the probe connects
reference/fips-lr2021/scripts/flash-e80-s3.sh
```
