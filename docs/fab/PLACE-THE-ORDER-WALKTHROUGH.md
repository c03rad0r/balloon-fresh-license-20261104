# Placing the JLCPCB order — 10 assembled v10 hub boards

Everything below is already in the repo and verified. You need to do the upload and the payment;
`AGENTS.md:153` puts purchase orders outside what the assistant may do.

Board of record: `docs/analysis/bulk-route-20261107/latest.kicad_pcb`, SHA256 prefix **`92ff3705`**.
If the board you package is not `92ff3705`, stop and say so — every number in this sheet is tied to it.

---

## Step 0 — Build the upload set (5 minutes)

Run this from the repo root. It packages exactly what JLC needs and refuses if the board hash is wrong:

```bash
cd ~/worktrees/pr-bulk-route-20261107
B=docs/analysis/bulk-route-20261107
test "$(git hash-object $B/latest.kicad_pcb | cut -c1-8)" = "92ff3705" && echo "board OK" || echo "WRONG BOARD - STOP"

OUT=~/jlc-upload-92ff3705
rm -rf "$OUT" && mkdir -p "$OUT"

# 1. Gerbers + drill, generated fresh from the board of record
kicad-cli pcb export gerbers --no-x2 --subtract-soldermask -o "$OUT/gerbers/" $B/latest.kicad_pcb
kicad-cli pcb export drill   --format excellon --drill-origin absolute \
                             --excellon-units mm -o "$OUT/gerbers/" $B/latest.kicad_pcb
(cd "$OUT/gerbers" && zip -q ../GERBERS.zip *.g* *.drl)

# 2. BOM and CPL that JLC reads
cp $B/assembly-partial/asm-bom-jlc.csv   "$OUT/BOM.csv"
cp $B/assembly-partial/asm-cpl-jlc.csv   "$OUT/CPL.csv"

ls -la "$OUT" "$OUT/gerbers"
```

**What you should see:** `GERBERS.zip`, `BOM.csv`, `CPL.csv`, and 15 files in `gerbers/`
(13 gerber layers + 2 drill files). The drill file must contain **196 holes**.

Sanity check the drill before uploading — this is the number that catches a stale export:

```bash
grep -c '^X' "$OUT"/gerbers/*.drl | head
# expect 196 total across the .drl files
```

---

## Step 1 — Upload and set the PCB options

Go to **https://jlcpcb.com** → *Order Now* → *Add gerber file* → upload `GERBERS.zip`.

JLC will show a thumbnail. **Look at it.** Confirm the outline is 72.10 × 80.10 mm and that the
board is not mirrored. If the image looks like the back of the board, your gerbers are flipped —
stop.

Set these options:

- **Base material** FR-4 · **Layers** 4 · **Dimensions** 72.1 × 80.1 mm (auto)
- **PCB Qty** **10**
- **Product type** *Industrial/Consumer electronics* (cheapest that allows assembly)
- **Delivery format** *Single PCB*
- **PCB thickness** 1.6 mm · **Impedance** No
- **PCB color** any (green is cheapest; colour does not affect function)
- **Surface finish** **HASL (with lead)** — cheapest and fine here. ENIG only if you want it.
- **Gold fingers** No · **Castellated holes** No
- **Min hole size** 0.30 mm (matches our 0.300 vias; 0.200 appears only as U1's thermal pad)
- **Confirm production file** leave off
- **Electrical test** *Flying probe fully test* — **turn this ON.** It is the cheapest insurance
  against a shorted board and it is the only check that validates our 2931 tracks in copper.

Enable **SMT Assembly** on the same page and choose **Assemble top and bottom sides** — this board
has parts on both. Getting this wrong returns boards with the four bridge diodes missing.

---

## Step 2 — BOM and CPL

Upload `BOM.csv` and `CPL.csv` where JLC asks.

**Expected result: 23 placements matched, 0 unmatched, 0 unmatched parts.**

If JLC reports unmatched lines, **do not proceed** — tell me the part numbers it could not match
and I will resolve them. Do not accept substitutions silently; a wrong LDO or a wrong bulk cap is
a dead board.

The BOM is 14 lines / 23 placements. All LCSC numbers are already filled. The hand-fit parts
(4× wing socket `J_W1..4`, `U_LORA1280`, `U3`) are **deliberately not in this BOM** — you solder
those, they are not JLC parts.

Check the placement preview against the CPL: parts should sit on their silkscreen outlines. Rotate
nothing by hand unless a footprint is visibly wrong.

---

## Step 3 — Things JLC will ask that we have answers for

- **"Do you want to panelise?"** No, single PCB.
- **"Any special process notes?"** No.
- **"Is this a prototype?"** Yes.
- **Extended parts fee** — $3 per unique extended LCSC part, 9 extended numbers = **$27**.
  This is expected; it is in the $69.71 estimate. Do not let it surprise you at checkout.
- **Engineering fee** $8. **Joint fee** ~$3.60.

Total for 10 assembled boards should land near **$69.71** plus shipping. If the cart shows a very
different number, something is misconfigured — screenshot it and show me before paying.

---

## Step 4 — Pay, then tell me

Place the order. Keep the order number.

When it arrives, the first thing to do is **not** power it. Do this:

1. Visual: check for solder bridges on `U1` (the ESP32 module, 1.27 mm pitch).
2. Continuity: `+3V3` to `GND` must **not** beep. If it beeps, stop.
3. Power the board from the bench supply at 3.3 V, **current limit 100 mA**, and watch the draw.
   A healthy board idles in the tens of mA after the ESP32 boots.

The two bodge wires and the hand-fit parts go on after that smoke test passes, not before.

---

## What this board is, and is not

It is a **bring-up and telemetry board**: ESP32-S3, two LoRa radios on a shared SPI1 bus, power
path from the wing sockets, supercap storage.

It is **not** a cut controller. `U_CUT1..4` are placeholder footprints — their value string is
literally `"latched cut driver + cut-sense (part TODO(unverified))"`. Pads 4/5/6 have no net at
all. The board cannot fire nichrome. That is a v11 schematic job (ADR-145 records the GPIO
roadmap), not something the order can fix.

Three nets remain unrouted and stay that way: `/EN` and `/IO0` (flash-time only, the ROM
bootloader needs neither), and `/F33_VSENSE` (a 43.7 mm run that must cross two full-board pours;
it measures a rail whose only load is the DNP PA, so it reads zero harmlessly).
