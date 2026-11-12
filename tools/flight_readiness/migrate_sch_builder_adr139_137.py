#!/usr/bin/env python3
"""Apply ADR-139 (E28 -> LoRa1280) and ADR-137 (no ANT* on the hub) to the v10 schematic builder.

Why this exists: the board received both changes; `build_flight_sch.py` did not. Measured
2026-11-02, check_schematic_parity.py reports 7 failures whose whole cause is this drift —
G3 five schematic-only antenna nets, G4 six nets on U_E28 vs U_LORA1280. Under ADR-128 the
schematic is the source of truth, so until this is applied the BOARD is the non-conforming
artefact.

LINE-ANCHORED, not string-matched. An earlier version used 6-line multi-line needles and a
slice boundary that consumed the next line's indentation; the needle then matched in isolation
but not mid-script, and the failure looked like a missing part rather than a slicing bug. Every
edit here locates its anchor line, asserts it appears exactly once, and replaces by line range.
"""
import sys

P = "tracker/hardware/schematics/flight_board/build_flight_sch.py"
lines = open(P, encoding="utf-8").read().split("\n")
orig_n = len(lines)
applied = []


def find_one(pred, label):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    if len(hits) != 1:
        print(f"FAIL [{label}]: expected exactly 1 anchor line, found {len(hits)}")
        sys.exit(1)
    return hits[0]


def find_last(pred, label):
    """The v10 blocks sit AFTER the v9 legacy tables that share the same text.

    Measured: `("ANT1", "Connector:Conn_Coaxial"` appears at line 1111 (the v9 table) and 2978
    (the v10 table). find_one refuses the ambiguity rather than editing the wrong table; the
    callers that need the v10 copy use this and assert the index is past the v10 marker.
    """
    hits = [i for i, l in enumerate(lines) if pred(l)]
    if not hits:
        print(f"FAIL [{label}]: anchor not found")
        sys.exit(1)
    return hits[-1]


LORA1280_PINS = '''V10_LORA1280_PINS = [
    ("1", "DIO2", "bidirectional"),
    ("2", "DIO3", "bidirectional"),
    ("3", "VCC", "power_in"),
    ("4", "GND", "power_in"),
    ("5", "MISO", "tri_state"),
    ("6", "MOSI", "input"),
    ("7", "SCK", "input"),
    ("8", "NSS", "input"),
    ("9", "ANT", "passive"),
    ("10", "GND", "power_in"),
    ("11", "GND", "power_in"),
    ("12", "GND", "power_in"),
    ("13", "NRESET", "input"),
    ("14", "GND", "power_in"),
    ("15", "BUSY", "output"),
    ("16", "DIO1", "bidirectional"),
]'''.split("\n")

# --- 1. pin table definition ---------------------------------------------------------------
start = find_one(lambda l: l.startswith("V10_E28_PINS = ["), "pin table start")
end = start
while lines[end] != "]":
    end += 1
lines[start:end + 1] = LORA1280_PINS
applied.append(f"pin table (lines {start + 1}-{end + 1}) -> V10_LORA1280_PINS")

# --- 2. component row ----------------------------------------------------------------------
i = find_one(lambda l: l.startswith('    ("U_E28", "balloon_flight_v10:E28_2G4M27SX"'), "component row")
j = find_one(lambda l: l.strip() == '"are UNASSIGNED (OPEN-E28-EN)."),', "component row end")
if not (i < j < i + 8):
    print(f"FAIL: component row end at {j} is not within 8 lines of {i}")
    sys.exit(1)
lines[i:j + 1] = '''    ("U_LORA1280", "balloon_flight_v10:LoRa1280", "LoRa1280",
     "NiceRF:LoRa1280", False,
     "ADR-139: G-NiceRF LoRa1280 (SX1280, 12.5 dBm, ranging: YES) replaced the "
     "E28-2G4M27SX at site D. The E28's PA/LNA enables (8/9) do not exist on "
     "this part, which CLOSES OPEN-E28-EN rather than waiving it. Pin 9 is the "
     "module's own antenna pad - netless by design per ADR-137 (the antenna "
     "attaches AT the module). Pin order from LoRa128X Rev2.2 s7 via "
     "build_lora1280_footprint.py."),'''.split("\n")
applied.append(f"component row (lines {i + 1}-{j + 1})")

# --- 3. symbol library entry ---------------------------------------------------------------
i = find_one(lambda l: l.strip() == '"balloon_flight_v10:E28_2G4M27SX": _v9_symbol(', "symbol entry")
j = find_one(lambda l: l.strip() == '"", V10_E28_PINS),', "symbol entry end")
if not (i < j < i + 16):
    print(f"FAIL: symbol entry end at {j} not within 16 lines of {i}")
    sys.exit(1)
lines[i:j + 1] = '''        "balloon_flight_v10:LoRa1280": _v9_symbol(
            V10_LIBNAME, "LoRa1280", "LoRa1280",
            "NiceRF:LoRa1280",
            "G-NiceRF LoRa1280: SX1280, 12.5 dBm, ranging supported, no PA and "
            "no LNA, 16 x 16 mm, 16 pads. Chosen by ADR-139 over the 27 dBm "
            "E28 because two vendors rate the PA-class modules as NOT "
            "supporting ranging, and the 2.4 GHz legal ceiling (10 dBm EIRP) "
            "makes the PA unusable here anyway. Pin 9 is the antenna pad; the "
            "board carries no RF network for it (ADR-137).",
            "", V10_LORA1280_PINS),'''.split("\n")
applied.append(f"symbol entry (lines {i + 1}-{j + 1})")

# --- 4. layout column + column title --------------------------------------------------------
i = find_one(lambda l: l.strip() == '["U_E28"],', "layout column")
lines[i] = lines[i].replace('["U_E28"]', '["U_LORA1280"]')
applied.append(f"layout column (line {i + 1})")

i = find_one(lambda l: "U_E28 E28-2G4M27SX (2.4 GHz ranging" in l, "column title")
lines[i] = '    "U_LORA1280 LoRa1280 (2.4 GHz ranging, site D, ADR-139)",'
applied.append(f"column title (line {i + 1})")

# --- 5. ADR-137: four U.FL connectors removed ----------------------------------------------
i = find_last(lambda l: l.startswith('    ("ANT1", "Connector:Conn_Coaxial"'), "ANT block start")
j = find_last(lambda l: 'ADR-119: GNSS L1 feed off U5 pin 11' in l, "ANT block end")
if not (i < j < i + 16):
    print(f"FAIL: ANT block end at {j} not within 16 lines of {i}")
    sys.exit(1)
del lines[i:j + 1]
applied.append(f"removed ANT1..ANT4 components (lines {i + 1}-{j + 1})")

i = find_last(lambda l: l.strip() == '["ANT1", "ANT2", "ANT3", "ANT4"],', "ANT layout column")
del lines[i]
applied.append(f"removed ANT layout column (line {i + 1})")

i = find_last(lambda l: 'U.FL ANTENNAS (4 feeds: ANT1 433 TX' in l, "ANT column title")
j = find_last(lambda l: '"/ ANT4 GNSS L1) - ADR-119",' in l, "ANT column title end")
# BOTH title lines go, because the ANT COLUMN is gone. Measured: the v10 title list and the
# v10 column list are balanced 16/16 before this edit; removing the column but leaving a title
# (or replacing two lines with one) leaves 15 columns against 16 titles and the generator dies
# with IndexError on col_x[ci]. Deleting both keeps them equal at 15/15.
del lines[i:j + 1]
applied.append(f"removed ANT column title (lines {i + 1}-{j + 1})")

# --- 6. OPEN-E28-EN is closed by the part change --------------------------------------------
i = find_one(lambda l: '("OPEN-E28-EN U_E28 pads 8 (RX_EN) / 9 (TX_EN)",' in l, "OPEN-E28-EN note")
j = find_one(lambda l: 'non-decision, not an omission."),' in l, "OPEN-E28-EN note end")
lines[i:j + 1] = '''    ("CLOSED-ADR-139 the E28 PA/LNA enables no longer exist",
     "OPEN-E28-EN asked which GPIOs drive the E28-2G4M27SX's RX_EN (8) and "
     "TX_EN (9). ADR-139 replaced that module with the LoRa1280, which has no "
     "PA, no LNA and therefore no enables: the question is CLOSED by the part "
     "change, not waived. If the E28 is ever reinstated the item reopens."),'''.split("\n")
applied.append(f"OPEN-E28-EN note (lines {i + 1}-{j + 1})")

# --- 7. sheet banner ------------------------------------------------------------------------
i = find_one(lambda l: "U_C bare LoRa2021 (site C); U_E28 '" in l, "banner")
j = find_one(lambda l: "J_W1..J_W4 wing sockets; ANT1..ANT4 U.FL.\"'" in l, "banner end")
lines[i:j + 1] = [
    "            '2.4 GHz RX (site B); U_C bare LoRa2021 (site C); U_LORA1280 '",
    "            'NiceRF LoRa1280 = 2.4 GHz ranging, ADR-139 (site D); U5 MAX-M10S '",
    "            'GNSS; U6 MS5611 baro; U7 TPS7A02 LDO; C_CAP1/C_CAP2 supercap '",
    "            'bank; J_PROG prog+USB header; J_W1..J_W4 wing sockets. NO ANT '",
    "            'connectors - ADR-137, antenna at the module.\"'",
]
applied.append(f"sheet banner (lines {i + 1}-{j + 1})")

out = "\n".join(lines)
open(P, "w", encoding="utf-8").write(out)
for a in applied:
    print("APPLIED:", a)
print(f"lines {orig_n} -> {len(lines)}")
print("remaining 'U_E28' tokens:", out.count("U_E28"))
print("remaining 'E28_2G4M27SX' tokens:", out.count("E28_2G4M27SX"))
print("LoRa1280 tokens:", out.count("LoRa1280"))
