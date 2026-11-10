# Flash Queue — Board Access Coordination

> **NO flashing without orchestrator (balloon-hermes) approval.**
> Sub-managers escalate flash requests to the orchestrator.

## Active Queue

| track | board | purpose | requested_time | approved_by | duration | status |
|-------|-------|---------|----------------|-------------|----------|--------|
| balloon-range-tests | E80 #1+#2 | PRBS-15 harmonization: E80 flashed+verified, C3 not connected | 2026-08-20T09:00Z | felix (orchestrator) | 8m | DONE (PARTIAL) |
| balloon-range-tests | E80 TX (#1) | BUF-T3 flash smoke: SWD flash e80_bench.bin (buf/t2-impl 91cd0ae + NVIC fix) + 10x 4KB BUF LOAD + src=BUF/src=PRBS gates | 2026-08-21T08:30Z | kanban t_dd4e516b (pre-approved) | 15m | DONE |
| balloon-range-tests | E80 RX (#2) | BUF-T5a: SWD flash e80_bench.bin (buf/t5a-rx-pcrc16) + verify PKT lines carry pcrc16 field | 2026-08-21T16:00Z | kanban t_a2949a8d (pre-approved) | 15m | DONE |
| balloon-rfa | E80 #1 (x240) + #2 (x280) | RFA-1b PRAM experiment: flash e80_bench.bin + PATCH ON|OFF arms (kanban t_0eaed49b, approved on main via PR #161 rows) | 2026-10-14T00:20Z | Felix (orchestrator, Signal) | 60m | **NOT FLASHED** — SWD 3-wire link not seated (probe initialises, IDR unreadable) + UART ROM-ISP does NOT work through the CH340: `FLASH` jumped (`OK JUMPING TO BOOTLOADER`) but stm32flash could not sync at 57600/115200/9600 8E1 and a bounded 8E1+8N1 sync-spam probe at 57600/115200/9600/38400 got no 0x79 ACK. Boards needed a USB replug (board B sat in the ROM bootloader, board A was IWDG-active); both replugged 2026-10-14 and back on fw 5fa7912. **Resolver 2026-10-14: flash arms RETIRED as moot** — the PRAM hypothesis is refuted as stated (the 64B/128B anomaly does not reproduce on fw 5fa7912; it came from pre-FIX-T3 fw c31fb30). No flash path needed. Details: docs/RFA1b-PRAM-PATCH-VERDICT-2026-10-14.md §5 |
| balloon-rfa | E80 #1 TX (x240) | RFA-1c recal-on-rate-change (kanban t_0393892c): SWD flash `build-fw/e80_bench.bin` fw=77b2663 sha256 ae4b589f68f8fad070ab2b05a9f51183b29b5b9443b8e178a4508131e452d9c4 (branch feat/rfa1c-recal-on-rate-change), then the 7-cell 260/650 interleave twice -> every cell rx_pkts=200 crc_ok=200 | 2026-10-14T11:40Z | REQUESTED (physical gate) | 20m | **BLOCKED (pre-flight, no write attempted)** — SWD link on x240 is still dead: openocd 0.12.0 reaches the CMSIS-DAP probe (148757200D2D1425), initialises SWD, then `Error: Error connecting DP: cannot read IDR` at 100/200/500/1000 kHz and with `reset_config srst_only srst_nogate`. The RX board is on x280 whose host has no debug probe, so SWD is not available for it either, and UART ROM-ISP is architected dead through the CH340 (see the RFA-1b row) with the TX board IWDG-active (`FLASH` refused until a power cycle). Human action needed: re-seat SWDIO/SWCLK/GND on the E80 TX board and power-cycle it. **UPDATED 2026-10-14 after the pre-flash matrix (`docs/rfa/RFA1c-RECAL-ON-RATE-CHANGE-2026-10-14.md`): the deaf end is the RECEIVER, so the RX board must be flashed too — x280 has no debug probe, so the probe has to move to the RX side (or the RX board to the probe). A TX-only flash will not satisfy the acceptance matrix: bring-up re-run on the TX alone = 1/3 clean on the 650-after-260 cells, on the RX = 2/3 clean (3/3 heard), on both ends = 3/3 clean in two consecutive runs.** |

| balloon-tollgate | archipelago LR2021 FIPS pair: S3 `34:85` (0.4.23) + NiceRF C3 `B0:A6` (0.5.13), not TollGate board-A/B/C | FIPS-2400-511: bounded 511-byte RX/SPI buffers + u16 FLRC packet length; host 42/42, FIPS 27/27 + native 4/4, both ESP-IDF builds pass; EU2400/511 reciprocal PER then throughput. Images staged `/tmp/opencode/fips-throughput/{s3,c3}` | 2026-11-10T18:45Z | PENDING — orchestrator approval required | 30m | **REQUESTED (not flashed)** |

## Rules

1. **NO flashing without orchestrator (balloon-hermes) approval**
2. **Sub-managers escalate flash requests to orchestrator** — do NOT flash autonomously
3. **Lock must be acquired BEFORE flashing** — `BALLOON_TRACK=<track> python3 balloon-board-lock.py acquire <resource>`
4. **Use pio-flash.sh wrapper** (NOT raw `pio run -t upload`)
5. **Hard device lock is active** — `chmod 000` on `/dev/ttyACMx` blocks ALL raw tool access
6. **picotool/openocd PATH shims active** — raw tool invocations are intercepted

## Walk Test Protocol (2026-07-24 Lesson)

During the 2026-07-24 walk test, 5 board-lock thefts occurred because:
- flock is advisory-only (doesn't block `cat`, `pio upload`, `picotool`)
- Sub-managers bypassed pio-flash.sh and ran raw `pio run -t upload`
- Multiple binaries deployed during the test — firmware mismatch made data unreliable

**This is now prevented by:**
- **Hard device lock**: `chmod 000 /dev/ttyACMx` on lock acquire (Phase 2a)
- **PATH shims**: picotool/openocd refuse to run without a lock (Phase 2b)
- **Flash queue**: this document — all flash requests must be approved (Phase 2c)
- **pio-flash.sh fix**: uses `balloon-board-lock.py check` for reliable verification (Phase 2d)

## How to Request a Flash

1. **Sub-manager**: Add a row to the queue table above with your request
2. **Orchestrator**: Review and approve (set `approved_by` and `status=APPROVED`)
3. **Sub-manager**: Acquire lock and flash:
   ```bash
   export BALLOON_TRACK=<your-track>
   python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both --purpose "approved flash: <reason>"
   ./tools/pio-flash.sh <env> --upload-port /dev/ttyACMx
   python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release both
   ```
4. **Update queue**: Set `status=DONE` when complete
