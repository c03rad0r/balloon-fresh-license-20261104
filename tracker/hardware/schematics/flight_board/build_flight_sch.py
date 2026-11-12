#!/usr/bin/env python3
"""Derive a loading KiCad 9 schematic for the C3 flight board FROM the frozen PCB.

Direction of truth: the placed/routed PCB (`output/v8i_krt_gnss.kicad_pcb`)
plus the tested firmware are authoritative; this generated schematic is a MIRROR of
that netlist, never the other way round.  Nothing here invents connectivity: every
net, every pin and every declared no-connect is read out of the PCB file.

Outputs (all regenerated deterministically from the PCB sha256 in the header):
  v_c3_flight.kicad_sch   the schematic
  sym-lib-table           library table so ERC resolves the embedded lib_symbols
  balloon_flight.kicad_sym  custom symbols (LR2021F33) as a real library
  balloon_flight.pretty   the PCB's own footprints, exported verbatim
  fp-lib-table            footprint library table so Footprint fields resolve

Run:  python3 build_flight_sch.py
"""
import hashlib
import itertools
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

# The F33 land pattern is DERIVED from the vendor's own land file at generation
# time (scripts/gen_f33_landpattern.py), never copied from a hand-maintained
# custom.pretty file.  That script exits 2 if the vendor file will not decode or
# fails its own self-checks, so a stale/hand-edited F33 pattern cannot re-enter
# the v9 design of record unnoticed.
sys.path.insert(0, os.path.join(REPO, "scripts"))
import gen_f33_landpattern as F33GEN  # noqa: E402

PCB = os.path.join(REPO, "tracker", "hardware", "output",
                   "v8i_krt_gnss.kicad_pcb")
OUT_SCH = os.path.join(HERE, "v_c3_flight.kicad_sch")
OUT_LIBTABLE = os.path.join(HERE, "sym-lib-table")
OUT_FPLIB = os.path.join(HERE, "balloon_flight.pretty")
OUT_FPTABLE = os.path.join(HERE, "fp-lib-table")
OUT_CUSTOM_SYM = os.path.join(HERE, "balloon_flight.kicad_sym")
SYMDIR = "/usr/share/kicad/symbols"
FP_LIBNAME = "balloon_flight"

FROZEN_SHA256 = "638de56387721460100cd3048fb23229294f510f0a2d89795026c7e6c0cfd0ea"

POWER_NETS = ("+3V3", "GND")

def merge_lib_table(path, kind, entries):
    """Additively merge `(lib ...)` rows into a KiCad library table.

    The v_c3 / v9 / v10 targets all write into the SAME shared project-local
    table files (sym-lib-table, fp-lib-table).  Rewriting them outright from
    one target would leave the OTHER two sheets with dangling
    lib_symbol_issues / footprint_link_issues warnings, so merge instead:
    keep every row already present, append only the missing ones.  Idempotent.
    """
    lines = []
    have = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        for ln in lines:
            m = re.match(r'\s*\(lib \(name "([^"]+)"\)', ln)
            if m:
                have.add(m.group(1))
    while lines and lines[-1].strip() == ")":
        lines.pop()
    if not lines:
        lines = ["(%s" % kind, "\t(version 7)"]
    added = []
    for (name, uri, descr) in entries:
        if name in have:
            continue
        lines.append('\t(lib (name "%s")(type "KiCad")(uri "%s")(options "")'
                     '(descr "%s"))' % (name, uri, descr))
        added.append(name)
    lines.append(")")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return added



# footprint lib-id -> schematic symbol lib-id.  Identity where the KiCad v9
# libraries carry a symbol for the same part.
PART_MAP = {
    "Resistor_SMD:R_0402_1005Metric": "Device:R",
    "Capacitor_SMD:C_0402_1005Metric": "Device:C",
    "Capacitor_SMD:C_0603_1608Metric": "Device:C",
    "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm": "Device:C_Polarized",
    "Diode_SMD:D_SOD-123": "Device:D_Schottky",
    "LED_SMD:LED_0603_1608Metric": "Device:LED",
    "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical":
        "Connector_Generic:Conn_01x02",
    "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical":
        "Connector_Generic:Conn_01x04",
    "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical":
        "Connector_Generic:Conn_01x06",
    "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical":
        "Connector:Conn_Coaxial",
    "RF_Module:ESP32-C3-WROOM-02": "RF_Module:ESP32-C3-WROOM-02",
    "RF_Module:HOPERF_RFM9XW_SMD": "balloon_flight:LR2021F33",
    "custom:LoRa2021_Castellated": "balloon_flight:LR2021F33",
    "MountingHole:MountingHole_2.2mm_M2": "Mechanical:MountingHole",
    "RF_GPS:ublox_MAX": "RF_GPS:MAX-M10S",
    "Package_TO_SOT_SMD:SOT-23-5": "Regulator_Linear:TPS7A0533PDBV",
    "Package_LGA:Bosch_LGA-8_2.5x2.5mm_P0.65mm_ClockwisePinNumbering":
        "Sensor:BME280",
    "Package_LGA:LGA-8_3x5mm_P1.25mm":
        "Sensor:BME280",
}

# Barometer: design intent is MS5611-01BA (10-1200 hPa) for the stratospheric flight
# profile. The frozen S0 placement PCB still labels this footprint as BMP280 because
# it predates the operator decision to switch; the generated schematic/netlist must
# reflect the intended part.  The BME280 *symbol* (Sensor:BME280) is used because it
# shares the BMP280 clockwise LGA-8 pad numbering that the board is wired for; only
# the Value and Footprint fields are overridden to MS5611-01BA / LGA-8_3x5mm_P1.25mm.
BARO_REF = "U5"
BARO_VALUE = "MS5611-01BA"
BARO_FOOTPRINT = "Package_LGA:LGA-8_3x5mm_P1.25mm"
# Custom inline symbol: the LR2021 Gen4 LoRa module as the board actually wires it.
# The board uses the 18-pin castellated LoRa2021_Castellated footprint; pad names
# below are derived from the v8i board netlist, with un-routed pads left neutral.
LR2021_PINS = [
    ("1", "VCC"), ("2", "GND"), ("3", "MISO"), ("4", "MOSI"),
    ("5", "SCK"), ("6", "NSS"), ("7", "BUSY"), ("8", "GND"),
    ("9", "ANT"), ("10", "PAD10"), ("11", "GND"), ("12", "GND"),
    ("13", "PAD13"), ("14", "RESET"), ("15", "DIO0"), ("16", "PAD16"),
    ("17", "PAD17"), ("18", "GND"),
]

# Pads declared deliberately unconnected (INTENTIONAL rows of the audit).
INTENTIONAL_NC = {
    ("J1", "6"), ("U3", "4"), ("U3", "5"), ("U3", "13"),
    ("U3", "14"), ("U3", "16"), ("U3", "17"),
}
# Pads in the audit whose GAP verdict is still open (PCB-S0b owns the ruling).
DECLARED_GAP = {
    ("U2", "10"): "TODO(unverified): LoRa2021 Gen4 pad 10 function / termination",
    ("U2", "13"): "TODO(unverified): LoRa2021 Gen4 pad 13 function / termination",
    ("U2", "16"): "TODO(unverified): LoRa2021 Gen4 pad 16 function / termination",
    ("U2", "17"): "TODO(unverified): LoRa2021 Gen4 pad 17 function / termination",
    ("U3", "15"): "TODO(unverified): MAX-M10S VIO_SEL tie-off required",
    ("U3", "18"): "TODO(unverified): MAX-M10S ~SAFEBOOT inactive level tie-off required",
    ("U4", "4"): "TODO(unverified): TPS7A02 pin 4 function / tie-off",
}

# Functional column layout: (column index, ordered refs)
COLUMNS = [
    ["SOLAR", "D1", "C_CAP", "U4", "C1", "C3", "R_DIV1", "R_DIV2"],
    ["U1", "C2", "C4", "R_PD", "R_LED", "LED1"],
    ["U2", "ANT1"],
    ["U3", "ANT2", "R_SER", "C_SH1", "C_SH2"],
    ["U5", "J1", "J2"],
    ["MNT1", "MNT2", "MNT3", "MNT4"],
]
COLUMN_TITLES = [
    "SOLAR INPUT / SUPERCAP / 3V3 LDO",
    "ESP32-C3-WROOM-02 + SUPPORT",
    "LR2021F33 RADIO (18-pin castellated)",
    "MAX-M10S GNSS + ANT2 FEED",
    "MS5611 + PROGRAMMING / DEBUG HEADERS",
    "MOUNTING HOLES",
]


# ---------------------------------------------------------------- helpers
# DETERMINISTIC uuids.  The .kicad_sch is a build product: regenerating it from
# the same PCB must be byte-identical, otherwise the recorded sha256 is not
# provenance and every re-run churns the diff.  uuid5 over a fixed namespace
# plus a per-run sequence is stable because the generator walks the board file
# in file order (no sets, no dicts built from unordered input).
UID_NAMESPACE = uuid.UUID("b4a1c0de-0000-5000-a000-f1a5b0a1d0e0")
_uid_seq = itertools.count(1)


def uid():
    return str(uuid.uuid5(UID_NAMESPACE, "flight-sch-%06d" % next(_uid_seq)))


def fmt(v):
    s = "%.4f" % round(float(v) + 0.0, 4)
    s = s.rstrip("0").rstrip(".")
    return s if s and s != "-0" else "0"


def clean(text):
    """Kill float repr noise before it reaches KiCad's parser."""
    return re.sub(r"-?\d+\.\d{5,}", lambda m: fmt(float(m.group(0))), text)


def blocks_by_prefix(text, prefix):
    """Every balanced block in `text` whose first chars are `prefix`."""
    i = 0
    while True:
        i = text.find(prefix, i)
        if i < 0:
            return
        d = 0
        j = i
        while j < len(text):
            if text[j] == "(":
                d += 1
            elif text[j] == ")":
                d -= 1
                if d == 0:
                    yield text[i:j + 1]
                    break
            j += 1
        i = j + 1


def parse_pcb(path):
    text = open(path).read()
    footprints = []
    for blk in blocks_by_prefix(text, "\t(footprint "):
        fpid = re.search(r'\(footprint "([^"]+)"', blk).group(1)
        if ":" not in fpid:
            fpid = ":" + fpid
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk).group(1)
        value = re.search(r'\(property "Value" "([^"]*)"', blk).group(1)
        at = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)', blk)
        pads = []
        for pb in blocks_by_prefix(blk, "\t\t(pad "):
            num = re.search(r'\(pad "([^"]*)"', pb).group(1)
            nm = re.search(r'\(net \d+ "([^"]*)"\)', pb)
            npth = "np_thru_hole" in pb
            pads.append(dict(num=num, net=(nm.group(1) if nm else ""),
                             npth=npth))
        footprints.append(dict(ref=ref, value=value, fpid=fpid,
                               leaf=fpid.split(":", 1)[-1], raw=blk,
                               at=(float(at.group(1)), float(at.group(2))),
                               pads=pads))
    return footprints


def raw_symbol(lib, name):
    path = os.path.join(SYMDIR, lib + ".kicad_sym")
    text = open(path, errors="replace").read()
    head = '(symbol "%s"\n' % name
    i = text.find(head)
    if i < 0:
        raise KeyError("symbol %s:%s not in KiCad v9 libraries" % (lib, name))
    d = 0
    j = i
    while j < len(text):
        if text[j] == "(":
            d += 1
        elif text[j] == ")":
            d -= 1
            if d == 0:
                break
        j += 1
    return text[i:j + 1]


def load_lib_symbol(lib, name):
    """Raw block, with `(extends PARENT)` flattened and renamed to LIB:NAME.

    Many KiCad v9 parts (e.g. TPS7A0533PDBV) are *derived* symbols that carry no
    pins of their own - the pin table lives in the parent.  A schematic's
    lib_symbols cache cannot express `extends`, so the parent's drawing/pin
    sub-symbols are inlined here.
    """
    block = raw_symbol(lib, name)
    m = re.search(r'\n[ \t]*\(extends "([^"]+)"\)', block)
    if m:
        parent = m.group(1)
        praw = raw_symbol(lib, parent)
        kids = list(blocks_by_prefix(praw, '\t\t(symbol "'))
        if not kids:
            raise KeyError("%s extends %s but the parent has no unit symbols"
                           % (name, parent))
        inj = "\n".join(k.replace('(symbol "%s_' % parent,
                                 '(symbol "%s_' % name, 1) for k in kids)
        block = block.replace(m.group(0), "\n" + inj)
    head = '(symbol "%s"' % name
    if not block.startswith(head):
        raise KeyError("unexpected symbol head for %s:%s" % (lib, name))
    return '(symbol "%s:%s"' % (lib, name) + block[len(head):]


PIN_RE = re.compile(
    r'\(pin\s+(\S+)\s+\S+\s+\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)'
    r'\s*\(length\s+([-\d.]+)\)[\s\S]*?\(number\s+"([^"]+)"')


def symbol_pins(block):
    """{'1': {'x':0.0,'y':3.81,'a':270.0,'len':1.27,'type':'passive'}}"""
    out = {}
    for m in PIN_RE.finditer(block):
        out[m.group(6)] = dict(type=m.group(1), x=float(m.group(2)),
                               y=float(m.group(3)), a=float(m.group(4)),
                               length=float(m.group(5)))
    return out


def symbol_extent(block):
    """Rough lib-coord bbox from pins + rectangles, as (x0,y0,x1,y1)."""
    xs, ys = [], []
    for m in re.finditer(r'\(rectangle\s*\(start\s+([-\d.]+)\s+([-\d.]+)\)'
                         r'\s*\(end\s+([-\d.]+)\s+([-\d.]+)\)', block):
        xs += [float(m.group(1)), float(m.group(3))]
        ys += [float(m.group(2)), float(m.group(4))]
    for p in symbol_pins(block).values():
        xs.append(p["x"])
        ys.append(p["y"])
    if not xs:
        return (-5.0, -5.0, 5.0, 5.0)
    return (min(xs), min(ys), max(xs), max(ys))


DIR = {0.0: (1, 0), 90.0: (0, 1), 180.0: (-1, 0), 270.0: (0, -1)}


def pin_point(sym_x, sym_y, pin):
    """Absolute schematic coordinate of a pin's connection end (rot = 0)."""
    return (sym_x + pin["x"], sym_y - pin["y"])


def stub_end(sym_x, sym_y, pin, length):
    """Wire out of the pin, away from the symbol body, on the 1.27 grid."""
    ox, oy = DIR[pin["a"] % 360.0]
    px, py = pin_point(sym_x, sym_y, pin)
    return (px - ox * length, py + oy * length)


# ---------------------------------------------------------------- LR2021 custom symbol
def lr2021_symbol():
    body = []
    body.append('(symbol "balloon_flight:LR2021F33"')
    body.append("\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t\t(hide no)\n\t\t)")
    body.append("\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)")
    body.append('\t\t(property "Reference" "U"\n\t\t\t(at 0 16.51 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t)\n\t\t)")
    body.append('\t\t(property "Value" "LR2021F33"\n\t\t\t(at 0 -16.51 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t)\n\t\t)")
    body.append('\t\t(property "Footprint" "RF_Module:HOPERF_RFM9XW_SMD"\n'
                "\t\t\t(at 0 0 0)\n\t\t\t(effects\n\t\t\t\t(font\n"
                "\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n"
                "\t\t\t)\n\t\t)")
    ds = ("https://www.nicerf.com/pdf/lora2021f33-2g4-2w-high-power-high-speed-"
          "multi-band-lr2021-wireless-communication-module-v1.1.pdf")
    body.append('\t\t(property "Datasheet" "%s"\n\t\t\t(at 0 0 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)" % ds)
    body.append('\t\t(property "Description" "NiceRF LoRa2021F33-2G4 LR2021 '
                'module, 16-pad RFM9xW-style footprint"\n\t\t\t(at 0 0 0)\n'
                "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)")
    body.append('\t\t(symbol "LR2021F33_0_1"\n\t\t\t(rectangle\n'
                "\t\t\t\t(start -11.43 12.7)\n\t\t\t\t(end 11.43 -12.7)\n"
                "\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n"
                "\t\t\t\t\t(type default)\n\t\t\t\t)\n"
                "\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n"
                "\t\t\t)\n\t\t)")
    pins = []
    for idx, (num, name) in enumerate(LR2021_PINS):
        if idx < 8:
            x, y, ang = -13.97, 8.89 - idx * 2.54, 0
        else:
            x, y, ang = 13.97, -8.89 + (idx - 8) * 2.54, 180
        pins.append(
            "\t\t\t(pin passive line\n\t\t\t\t(at %s %s %s)\n"
            "\t\t\t\t(length 2.54)\n\t\t\t\t(name \"%s\"\n\t\t\t\t\t(effects\n"
            "\t\t\t\t\t\t(font\n\t\t\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t\t\t)\n\t\t\t\t\t)\n\t\t\t\t)\n"
            "\t\t\t\t(number \"%s\"\n\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n"
            "\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n\t\t\t\t\t)\n"
            "\t\t\t\t)\n\t\t\t)"
            % (fmt(x), fmt(y), fmt(ang), name, num))
    body.append('\t\t(symbol "LR2021F33_1_1"\n' + "\n".join(pins) + "\n\t\t)")
    body.append("\t)")
    return "\n".join(body)


# ---------------------------------------------------------------- PCB parsing
def resolve_symbol(fpid):
    if fpid in PART_MAP:
        return PART_MAP[fpid]
    leaf = fpid.split(":")[-1]
    for k, v in PART_MAP.items():
        if k.split(":")[-1] == leaf:
            return v
    raise KeyError("no symbol mapping for footprint %s (add to PART_MAP)" % fpid)


# ---------------------------------------------------------------- emit
def emit(footprints):
    lib_ids_used = []
    lib_blocks = {"balloon_flight:LR2021F33": lr2021_symbol()}
    resolved = []
    for fp in footprints:
        lib_id = resolve_symbol(fp["fpid"])
        if lib_id in lib_blocks:
            block = lib_blocks[lib_id]
        else:
            lib, name = lib_id.split(":")
            block = load_lib_symbol(lib, name)
            lib_blocks[lib_id] = block
        resolved.append(dict(fp=fp, lib_id=lib_id, block=block))
        if lib_id not in lib_ids_used:
            lib_ids_used.append(lib_id)

    # ---- validation: every numbered pad must have a pin in the symbol
    problems = []
    for r in resolved:
        pins = symbol_pins(r["block"])
        padnums = sorted({p["num"] for p in r["fp"]["pads"] if p["num"] != ""})
        missing = [n for n in padnums if n not in pins]
        if missing:
            problems.append("%s (%s -> %s): pads %s have no symbol pin"
                            % (r["fp"]["ref"], r["fp"]["fpid"], r["lib_id"], missing))
    if problems:
        print("PIN COVERAGE FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(2)

    # ---- footprint library: the PCB's own footprints, exported verbatim, so the
    # schematic Footprint fields resolve (ERC footprint_link_issues = 0)
    os.makedirs(OUT_FPLIB, exist_ok=True)
    written = set()
    for r in resolved:
        leaf = r["fp"]["leaf"]
        if leaf in written:
            continue
        written.add(leaf)
        blk = re.sub(r'\(footprint\s+"[^"]*"',
                     '(footprint "%s"\n\t\t(version 20241229)\n'
                     '\t\t(generator "pcbnew")\n\t\t(generator_version "9.0")'
                     % leaf, r["fp"]["raw"], count=1)
        with open(os.path.join(OUT_FPLIB, leaf + ".kicad_mod"), "w") as fh:
            fh.write(clean(blk) + "\n")
    with open(OUT_FPTABLE, "w") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "%s")'
                 '(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")(options "")'
                 '(descr "Flight board footprints exported from the frozen PCB"))'
                 '\n\t(lib (name "%s")(type "KiCad")'
                 '(uri "${KIPRJMOD}/v9_lib/%s.pretty")(options "")'
                 '(descr "v9 flight board footprints (F33 fixed pattern + bare '
                 'LoRa2021 + SX1280 UNVERIFIED)"))\n)\n'
                 % (FP_LIBNAME, FP_LIBNAME, V9_LIBNAME, V9_LIBNAME))

    # ---- layout
    by_ref = {r["fp"]["ref"]: r for r in resolved}
    unknown = [c for col in COLUMNS for c in col if c not in by_ref]
    if unknown:
        sys.exit("layout lists unknown refs: %s" % unknown)
    placed_refs = {c for col in COLUMNS for c in col}
    extra = [r["fp"]["ref"] for r in resolved if r["fp"]["ref"] not in placed_refs]
    if extra:
        sys.exit("PCB footprints missing from COLUMNS layout: %s" % extra)

    sizes = {}
    for ref, r in by_ref.items():
        x0, y0, x1, y1 = symbol_extent(r["block"])
        sizes[ref] = (x1 - x0, y1 - y0)

    col_x, x = [], 25.4
    for col in COLUMNS:
        w = max(sizes[ref][0] for ref in col)
        col_x.append(x)
        x += w + 22.86

    pos = {}
    for ci, col in enumerate(COLUMNS):
        y = 45.72
        for ref in col:
            _, h = sizes[ref]
            pos[ref] = (round(col_x[ci] / 1.27) * 1.27, round(y / 1.27) * 1.27)
            y += h + 20.32

    # ---- body
    body, notes = [], []
    body.append('\t(text "BALLOON C3 FLIGHT BOARD - netlist mirror of '
                'v8i_krt_gnss.kicad_pcb"\n\t\t(exclude_from_sim no)\n'
                '\t\t(at 25.4 25.4 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
                '(size 2.54 2.54)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                '\t\t)\n\t\t(uuid "%s")\n\t)' % uid())
    body.append('\t(text "PCB sha256 %s - schematic is DERIVED, the PCB is the '
                'source of truth (ADR-028)"\n\t\t(exclude_from_sim no)\n'
                '\t\t(at 25.4 30.48 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
                '(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                '\t\t)\n\t\t(uuid "%s")\n\t)' % (FROZEN_SHA256[:16] + "...", uid()))
    for ci, title in enumerate(COLUMN_TITLES):
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s 38.1 0)\n\t\t(effects\n\t\t\t(font\n'
                    '\t\t\t\t(size 1.524 1.524)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)'
                    % (title, fmt(round(col_x[ci] / 1.27) * 1.27), uid()))

    power_syms, wires, labels, ncs, flags = [], [], [], [], []
    stats = dict(pins=0, nets=set(), labels=0, power=0, nc=0, gap=0, unnamed=0)

    for r in resolved:
        ref, fp, lib_id = r["fp"]["ref"], r["fp"], None
        lib_id = r["lib_id"]
        sx, sy = pos[ref]
        pins = symbol_pins(r["block"])
        # design intent override for the barometer (frozen PCB labels it BMP280)
        value = BARO_VALUE if ref == BARO_REF else fp["value"]
        footprint = BARO_FOOTPRINT if ref == BARO_REF else "%s:%s" % (FP_LIBNAME, fp["leaf"])
        pin_txt = "".join('\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n' % (n, uid())
                          for n in padnums)
        body.append(
            "\t(symbol\n\t\t(lib_id \"%s\")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n"
            "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
            "\t\t(dnp no)\n\t\t(uuid \"%s\")\n"
            "\t\t(property \"Reference\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Value\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Footprint\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
            "%s\t\t(instances\n\t\t\t(project \"v_c3_flight\"\n"
            "\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference \"%s\")\n"
            "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n"
            % (lib_id, fmt(sx), fmt(sy), uid(), ref, fmt(sx + 2.54),
               fmt(sy - 6.35), value, fmt(sx + 2.54), fmt(sy + 2.54),
               footprint, fmt(sx), fmt(sy),
               pin_txt, uid(), ref))

        # netless-pad handling, keyed on the audit verdicts
        for pad in fp["pads"]:
            if pad["num"] == "":
                stats["unnamed"] += 1
                continue
            pin = pins[pad["num"]]
            px, py = pin_point(sx, sy, pin)
            stats["pins"] += 1
            key = (ref, pad["num"])
            if pad["net"] == "":
                ncs.append((px, py))
                stats["nc"] += 1
                if key in DECLARED_GAP:
                    stats["gap"] += 1
                    notes.append((px, py, "GAP %s.%s: %s"
                                  % (ref, pad["num"], DECLARED_GAP[key])))
                elif key not in INTENTIONAL_NC:
                    notes.append((px, py, "NETLESS %s.%s: unclassified"
                                  % (ref, pad["num"])))
                continue
            stats["nets"].add(pad["net"])
            ex, ey = stub_end(sx, sy, pin, 5.08)
            wires.append((px, py, ex, ey))
            if pad["net"] in POWER_NETS:
                power_syms.append((pad["net"], ex, ey))
                stats["power"] += 1
            else:
                labels.append((pad["net"], ex, ey))
                stats["labels"] += 1

    # ---- PWR_FLAG: rails fed only by connectors/passives need a driver
    flag_pts = {}
    for (net, x, y) in power_syms:
        flag_pts.setdefault(net, (x, y))
    for (net, x, y) in labels:
        flag_pts.setdefault(net, (x, y))
    flag_nets = {n for (n, _, _) in power_syms}
    for r in resolved:
        if r["fp"]["ref"] != "U4":
            continue
        for p in r["fp"]["pads"]:
            if p["num"] == "1" and p["net"]:
                flag_nets.add(p["net"])
    # a rail already driven by a real power-output pin needs no PWR_FLAG
    driven = set()
    for r in resolved:
        rpins = symbol_pins(r["block"])
        for p in r["fp"]["pads"]:
            if (p["num"] and p["net"]
                    and rpins.get(p["num"], {}).get("type") == "power_out"):
                driven.add(p["net"])
    flag_nets -= driven
    for net in sorted(flag_nets):
        if net not in flag_pts:
            continue
        x, y = flag_pts[net]
        wires.append((x, y, x + 5.08, y))
        flags.append((net, x + 5.08, y))

    for (x1, y1, x2, y2) in wires:
        body.append('\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
                    '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
                    '\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x1), fmt(y1), fmt(x2), fmt(y2), uid()))
    for (txt, x, y) in labels:
        body.append('\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n'
                    '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (txt, fmt(x), fmt(y), uid()))
    for i, (net, x, y) in enumerate(power_syms):
        pref = "#PWR0%03d" % (i + 1)
        body.append(('\t(symbol\n\t\t(lib_id "power:%s")\n\t\t(at %s %s 0)\n'
                    '\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                    '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                    '\t\t(property "Reference" "#PWR"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Value" "%s"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                    '\t\t(instances\n\t\t\t(project "v_c3_flight"\n'
                    '\t\t\t\t(path "/%s"\n\t\t\t\t\t(reference "#PWR")\n'
                    '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                    % (net, fmt(x), fmt(y), uid(), fmt(x + 2.54), fmt(y + 2.54),
                       net, fmt(x + 2.54), fmt(y - 2.54), fmt(x), fmt(y),
                       uid(), uid())).replace('#PWR', pref))
    for i, (net, x, y) in enumerate(flags):
        body.append('\t(symbol\n\t\t(lib_id "power:PWR_FLAG")\n\t\t(at %s %s 0)\n'
                    '\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                    '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                    '\t\t(property "Reference" "#FLG0%d"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Value" "PWR_FLAG"\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                    '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                    '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                    '\t\t(instances\n\t\t\t(project "v_c3_flight"\n'
                    '\t\t\t\t(path "/%s"\n\t\t\t\t\t(reference "#FLG0%d")\n'
                    '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                    % (fmt(x), fmt(y), uid(), i + 1, fmt(x + 2.54), fmt(y + 2.54),
                       fmt(x + 2.54), fmt(y - 2.54), fmt(x), fmt(y), uid(),
                       uid(), i + 1))
    for (x, y) in ncs:
        body.append('\t(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x), fmt(y), uid()))

    # gap / netless annotations: honest, visible, cites the audit
    seen_notes = set()
    for (x, y, txt) in notes:
        if txt in seen_notes:
            continue
        seen_notes.add(txt)
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n'
                    '\t\t\t\t(size 1.016 1.016)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (txt, fmt(x + 1.27), fmt(y), uid()))

    # power symbols come from the power library; make sure the defs exist
    for net in sorted({n for (n, _, _) in power_syms}):
        lib, name = "power", net
        if "power:" + net not in lib_blocks:
            block = load_lib_symbol(lib, name)
            lib_blocks["power:" + net] = block
    if flags and "power:PWR_FLAG" not in lib_blocks:
        lib_blocks["power:PWR_FLAG"] = load_lib_symbol("power", "PWR_FLAG")
    libdefs = "\n".join(lib_blocks[k] for k in lib_blocks)

    sch = ('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n'
           '\t(generator_version "9.0")\n\t(uuid "%s")\n\t(paper "A2")\n'
           '\t(title_block\n\t\t(title "Balloon C3 Flight Board")\n'
           '\t\t(date "2026-09-17")\n\t\t(rev "v0-derived")\n'
           '\t\t(company "Balloon Relay")\n'
           '\t\t(comment 1 "DERIVED artifact: mirrors the frozen PCB netlist; '
           'PCB is the source of truth (ADR-028)")\n\t)\n'
           '\t(lib_symbols\n%s\n\t)\n%s'
           '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n)\n'
           % (uid(), libdefs, "".join(body)))

    with open(OUT_SCH, "w") as fh:
        fh.write(clean(sch))

    # standalone symbol library for the custom parts (sym-lib-table resolves it)
    with open(OUT_CUSTOM_SYM, "w") as fh:
        fh.write('(kicad_symbol_lib\n\t(version 20241209)\n'
                 '\t(generator "kicad_symbol_editor")\n'
                 '\t(generator_version "9.0")\n')
        for k, blk in lib_blocks.items():
            if k.startswith(FP_LIBNAME + ":"):
                fh.write("\t" + blk.replace('(symbol "%s:' % FP_LIBNAME,
                                             '(symbol "', 1) + "\n")
        fh.write(")\n")

    libs = sorted({k.split(":")[0] for k in lib_blocks}
                  | {"Sensor_Pressure", "Diode", V9_LIBNAME})
    with open(OUT_LIBTABLE, "w") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n')
        for lib in libs:
            uri = (os.path.join(SYMDIR, lib + ".kicad_sym")
                   if lib not in ("balloon_flight", V9_LIBNAME)
                   else ("${KIPRJMOD}/balloon_flight.kicad_sym"
                         if lib == "balloon_flight"
                         else "${KIPRJMOD}/v9_lib/%s.kicad_sym" % V9_LIBNAME))
            fh.write('\t(lib (name "%s")(type "KiCad")(uri "%s")(options "")'
                     '(descr ""))\n' % (lib, uri))
        fh.write(")\n")

    stats["flags"] = len(flags)
    return stats, resolved


# =====================================================================
# v9 TRI-BAND FLIGHT BOARD  (ADR-029 / 108-f33-sx1280-pin-plan / 034 / 035 /
# 036-043)
# ---------------------------------------------------------------------
# The C3 schematic above is DERIVED from a frozen PCB sha256.  No v9 PCB
# exists, so this variant is a DESIGN-INTENT schematic instead: every net
# below is transcribed from a landed decision record (named in V9_NET_SRC),
# and every pin whose electrical treatment no record fixes is left OPEN with
# a visible TODO(unverified) note.  Nothing is guessed -- in particular no
# tie-off is invented for the 2 W PA module, for an RF port, or for a power
# pin whose rail the records leave open (ADR-029 O5).
# =====================================================================

V9_OUT_SCH = os.path.join(HERE, "v9_flight.kicad_sch")
V9_LIBDIR = os.path.join(HERE, "v9_lib")
V9_FPLIB = os.path.join(V9_LIBDIR, "balloon_flight_v9.pretty")
V9_SYMLIB = os.path.join(V9_LIBDIR, "balloon_flight_v9.kicad_sym")
V9_FPTABLE = os.path.join(HERE, "v9_fp-lib-table")
V9_SYMTABLE = os.path.join(HERE, "v9_sym-lib-table")
V9_PROJECT = "v9_flight"
V9_LIBNAME = "balloon_flight_v9"
V9_SRC_PRETTY = os.path.join(REPO, "tracker", "hardware", "hub_board_diy",
                             "custom.pretty")
V9_SX_FP = os.path.join(REPO, "tracker", "hardware", "footprints", "v9",
                        "SX1280_QFN24.kicad_mod")

# --- F33-2G4 18-pad module.  Pad names from docs/DUAL-VARIANT-DESIGN.md (V2
# table) + commit d5a2e47 (the corrected vendor land pattern, in base).
V9_F33_PINS = [
    ("1", "VCC", "power_in"), ("2", "GND", "power_in"),
    ("3", "GND", "power_in"), ("4", "GND", "power_in"),
    ("5", "CE", "input"), ("6", "GND", "power_in"),
    ("7", "GND", "power_in"), ("8", "GND", "power_in"),
    ("9", "ANT", "passive"),
    ("10", "ANT-2G4", "passive"), ("11", "GND", "power_in"),
    ("12", "SCK", "input"), ("13", "NSS", "input"),
    ("14", "BUSY", "output"), ("15", "MOSI", "input"),
    ("16", "MISO", "tri_state"), ("17", "RESET", "input"),
    ("18", "IRQ", "output"),
]

# --- bare LoRa2021 castellated 18-pad module.  Pad names from
# docs/DUAL-VARIANT-DESIGN.md (V1 table: GP2..GP8 wiring + "GND pins 2,8,11,12,18").
# Pad 13 is `VTCXO` (was the placeholder `PAD13_??`): the value vendor pin table
# docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf 7 "Pin definition"
# enumerates all 18 pads and names pad 13 `VTCXO`, `O`, "Can provide power for an
# external TCXO."  This is a NAMING correction with a source (ADR-058 s1.3), not a
# connectivity change: pad 13 carries the chip's VTCXO/VNTC rail (chip pin 6) and
# is the bias rail of the ADR-058 NTC temperature-compensation provision.
# NOTE: the module breaks out VTCXO but NOT the chip's `NTC` sense input (chip
# pin 3) - see OPEN-29 and ADR-058 D6.  Pads 16/17 are now NAMED `DIO8`/`DIO7` - a naming correction with a source (the vendor pin table docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf s7 and docs/inventory.md line 28), no connectivity added. Their MCU ASSIGNMENT is still OPEN (OPEN-5).
V9_BARE_PINS = [
    ("1", "VCC", "power_in"), ("2", "GND", "power_in"),
    ("3", "MISO", "tri_state"), ("4", "MOSI", "input"),
    ("5", "SCK", "input"), ("6", "NSS", "input"),
    ("7", "BUSY", "output"), ("8", "GND", "power_in"),
    ("9", "ANT", "passive"),
    ("10", "2G4_ANT", "passive"), ("11", "GND", "power_in"),
    ("12", "GND", "power_in"), ("13", "VTCXO", "passive"),
    ("14", "RESET", "input"), ("15", "IRQ_DIO9", "output"),
    ("16", "DIO8", "passive"), ("17", "DIO7", "passive"),
    ("18", "GND", "power_in"),
]

# --- SX1280.  REAL pinout, VERIFIED.  Source: Semtech SX1280/SX1281 Data Sheet Rev 3.2
# (March 2020) Table 2-1 + Figure 2-1, vendored at docs/sx1280/ -- transcribed to
# docs/fab/SX1280-WIRING-SPEC.json and docs/fab/OPEN-13-CLOSED-SX1280-PINOUT.md, and built into
# the sheet of record by commit b7b47df7 (STEP 1).
#
# The FOURTH field is the pin's REAL SIDE.  This is the whole point: the previous version of this
# table was a declared-unverified PLACEHOLDER (VDD_IN/VDD_IO/NSS/SCK/MOSI/MISO/ANT_SW) whose
# 25 entries were laid out by _v9_symbol()'s 50/50 half-split -- 13 left / 12 right at 2.54 mm --
# which is structurally unable to represent a part with 6 LEFT / 3 BOTTOM / 9 RIGHT / 6 TOP pins.
# The placeholder also gave the part an ANT_SW pin, which the real SX1280 does NOT have (that net
# was removed from the sheet in commit 96d219b3).
#
# ORDER MATTERS: pins are placed in list order along their own side, so this list is also the
# pin-escape order.  Pin 0 is the exposed pad, whose connectable end lands at the body CENTRE --
# that is what STEP 1 built and what the sheet's wiring assumes (it needs a dedicated wire run
# out to a ground flag).  Making the EP a normal side pin is a separate, still-open improvement.
V9_SX1280_PINS = [
    ("0",  "GND",     "passive",       "centre"),
    ("1",  "VR_PA",   "passive",       "LEFT"),
    ("2",  "VDD_IN",  "power_in",      "LEFT"),
    ("3",  "NRESET",  "input",         "LEFT"),
    ("4",  "XTA",     "passive",       "LEFT"),
    ("5",  "GND",     "passive",       "LEFT"),
    ("6",  "XTB",     "passive",       "LEFT"),
    ("7",  "BUSY",    "output",        "BOTTOM"),
    ("8",  "DIO1",    "bidirectional", "BOTTOM"),
    ("9",  "DIO2",    "bidirectional", "BOTTOM"),
    ("10", "DIO3",    "bidirectional", "RIGHT"),
    ("11", "VBAT_IO", "power_in",      "RIGHT"),
    ("12", "DCC_FB",  "passive",       "RIGHT"),
    ("13", "GND",     "passive",       "RIGHT"),
    ("14", "DCC_SW",  "passive",       "RIGHT"),
    ("15", "VBAT",    "power_in",      "RIGHT"),
    ("16", "MISO_TX", "output",        "RIGHT"),
    ("17", "MOSI_RX", "input",         "RIGHT"),
    ("18", "SCK_RTSN", "input",        "RIGHT"),
    ("19", "NSS_CTS", "input",         "TOP"),
    ("20", "GND",     "passive",       "TOP"),
    ("21", "GND",     "passive",       "TOP"),
    ("22", "RFIO",    "bidirectional", "TOP"),
    ("23", "GND",     "passive",       "TOP"),
    ("24", "GND",     "passive",       "TOP"),
]

# --- TPS7A02 3.3 V ultra-low-Iq LDO, SOT-23-5 (ADR-006).  Pin *names* follow the
# SOT-23-5 LDO convention the repo already uses (Regulator_Linear:TPS7A0533PDBV).
# The TPS7A02 pinout itself is not committed in-repo -> EN/NC treatment is TODO.
V9_TPS7A02_PINS = [
    ("1", "IN", "power_in"), ("2", "GND", "power_in"),
    ("3", "EN", "input"), ("4", "NC", "passive"), ("5", "OUT", "power_out"),
]


def _v9_symbol(libname, name, value, footprint, descr, datasheet, pins):
    """Build a balloon_flight_v9:<name> symbol from a pin table.

    TWO FORMS, and the difference matters:

    * 3-tuples (num, pname, etype) -- LEGACY.  Pins are split 50/50 left/right at 2.54 mm pitch,
      exactly like the LR2021F33 custom symbol the C3 generator emits (pins 1..N/2 left, rest
      right).  Unchanged; every other custom symbol on this sheet still uses it.

    * 4-tuples (num, pname, etype, side) with side in LEFT / BOTTOM / RIGHT / TOP / centre --
      the REAL SX1280 layout.  Pins are placed on their OWN side, spread evenly across the body,
      which is what a 6 LEFT / 3 BOTTOM / 9 RIGHT / 6 TOP part requires.  A 50/50 half-split
      CANNOT represent it: 25 pins that way is 13 left / 12 right at 2.54 mm, and that 13-row
      2.54 mm stub field is exactly the geometry that re-landed the old wiring on the wrong pins.
      The geometry below reproduces rewrite_sch_sx1280.py (STEP 1, commit b7b47df7) pin for pin,
      so the generator's symbol and the sheet of record stay identical.  A 'centre' pin is placed
      at the symbol origin -- that is the exposed pad, whose connectable end lands inside the body.
    """
    sided = bool(pins) and len(pins[0]) == 4
    if sided:
        groups = {}
        for num, pname, etype, side in pins:
            if side == "centre":
                continue
            groups.setdefault(side, []).append((num, pname, etype))
        bx, by, lead = 12.7, 17.78, 2.54
        for side in ("LEFT", "BOTTOM", "RIGHT", "TOP"):
            if side not in groups:
                continue
            grp = groups[side]
            n_side = len(grp)
            step = (by * 2 if side in ("LEFT", "RIGHT") else bx * 2) / (n_side + 1)
            for i, (num, pname, etype) in enumerate(grp):
                off = step * (i + 1)
                if side == "LEFT":
                    x, y, ang = -bx - lead, by - off, 0.0
                elif side == "RIGHT":
                    x, y, ang = bx + lead, -by + off, 180.0
                elif side == "BOTTOM":
                    x, y, ang = -bx + off, -by - lead, 90.0
                else:                                    # TOP
                    x, y, ang = bx - off, by + lead, 270.0
                groups[side][i] = (num, pname, etype, x, y, ang)
        centres = [(num, pname, etype, 0.0, 0.0, 0.0)
                   for num, pname, etype, side in pins if side == "centre"]
        body_pins = centres + [p for side in ("LEFT", "BOTTOM", "RIGHT", "TOP")
                               for p in groups.get(side, [])]
        body = [_v9_pin(num, pname, etype, x, y, ang)
                for num, pname, etype, x, y, ang in body_pins]
        out = _v9_symbol_head(libname, name, value, footprint, descr, datasheet, bx, by)
        out.append('\t\t(symbol "%s_1_1"\n%s\n\t\t)' % (name, "\n".join(body)))
        out.append("\t)")
        return "\n".join(out)

    half = (len(pins) + 1) // 2
    left, right = pins[:half], pins[half:]
    n = max(len(left), len(right))
    by = (n - 1) * 2.54 / 2.0 + 2.54
    bx = 12.7
    out = _v9_symbol_head(libname, name, value, footprint, descr, datasheet, bx, by)
    body = []
    for i, (num, pname, etype) in enumerate(left):
        body.append(_v9_pin(num, pname, etype, -bx - 2.54,
                            by - 2.54 - i * 2.54, 0.0))
    for i, (num, pname, etype) in enumerate(right):
        body.append(_v9_pin(num, pname, etype, bx + 2.54,
                            by - 2.54 - i * 2.54, 180.0))
    out.append('\t\t(symbol "%s_1_1"\n%s\n\t\t)' % (name, "\n".join(body)))
    out.append("\t)")
    return "\n".join(out)


def _v9_symbol_head(libname, name, value, footprint, descr, datasheet, bx, by):
    """Everything of a custom symbol before its pin body: headers, properties, body rectangle."""
    out = ['(symbol "%s:%s"' % (libname, name)]
    out.append('\t\t(pin_names\n\t\t\t(offset 1.016)\n\t\t\t(hide no)\n\t\t)')
    out.append('\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)')
    out.append('\t\t(property "Reference" "U"\n\t\t\t(at 0 %s 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t)\n\t\t)' % fmt(by + 2.54))
    out.append('\t\t(property "Value" "%s"\n\t\t\t(at 0 %s 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t)\n\t\t)' % (value, fmt(-by - 2.54)))
    out.append('\t\t(property "Footprint" "%s"\n\t\t\t(at 0 0 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)' % footprint)
    out.append('\t\t(property "Datasheet" "%s"\n\t\t\t(at 0 0 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)' % datasheet)
    out.append('\t\t(property "Description" "%s"\n\t\t\t(at 0 0 0)\n'
               '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
               '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)' % descr)
    out.append('\t\t(symbol "%s_0_1"\n\t\t\t(rectangle\n'
               '\t\t\t\t(start %s %s)\n\t\t\t\t(end %s %s)\n'
               '\t\t\t\t(stroke\n\t\t\t\t\t(width 0.254)\n'
               '\t\t\t\t\t(type default)\n\t\t\t\t)\n'
               '\t\t\t\t(fill\n\t\t\t\t\t(type background)\n\t\t\t\t)\n\t\t\t)\n\t\t)'
               % (name, fmt(-bx), fmt(by), fmt(bx), fmt(-by)))
    return out


def _v9_pin(num, pname, etype, x, y, ang):
    return ('\t\t\t(pin %s line\n\t\t\t\t(at %s %s %s)\n'
            '\t\t\t\t(length 2.54)\n\t\t\t\t(name "%s"\n'
            '\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n'
            '\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n'
            '\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t\t(number "%s"\n'
            '\t\t\t\t\t(effects\n\t\t\t\t\t\t(font\n'
            '\t\t\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t\t\t)\n'
            '\t\t\t\t\t)\n\t\t\t\t)\n\t\t\t)'
            % (etype, fmt(x), fmt(y), fmt(ang), pname, num))


def v9_custom_symbols():
    """The four repo-local symbols the v9 sheet needs (written to v9_lib/)."""
    return {
        "balloon_flight_v9:F33_2G4": _v9_symbol(
            V9_LIBNAME, "F33_2G4", "LoRa2021F33-2G4",
            "balloon_flight_v9:LoRa2021F33_2G4",
            "NiceRF LoRa2021F33-2G4 (SEMTECH LR2021, 18-pad castellated, "
            "built-in +30 dBm PA / 0.5 ppm TCXO). Pad names from "
            "docs/DUAL-VARIANT-DESIGN.md; pad centres from the vendor land "
            "file (d5a2e47), pad SIZE derived from the operator-supplied "
            "castellation hole diameter 0.80 +- 0.1 mm (datasheet s9 p8).",
            "https://www.nicerf.com/pdf/lora2021f33-2g4-2w-high-power-high-speed-"
            "multi-band-lr2021-wireless-communication-module-v1.1.pdf",
            V9_F33_PINS),
        "balloon_flight_v9:LR2021_BARE": _v9_symbol(
            V9_LIBNAME, "LR2021_BARE", "LoRa2021_Castellated",
            "balloon_flight_v9:LoRa2021_Castellated",
            "NiceRF LoRa2021 castellated (SEMTECH LR2021, 18-pad, "
            "chip-only 2.4 GHz RX under ADR-034 D1). Pad names from "
            "docs/DUAL-VARIANT-DESIGN.md V1 table. Land pattern UNVERIFIED "
            "against the vendor pad file (V9-RADIO-SITE-MATRIX open item 6).",
            "", V9_BARE_PINS),
        "balloon_flight_v9:SX1280": _v9_symbol(
            V9_LIBNAME, "SX1280", "SX1280",
            "balloon_flight_v9:SX1280_QFN24",
            "Semtech SX1280 2.4 GHz ranging transceiver. *** PIN NUMBERING "
            "AND LAND PATTERN NOT VERIFIED - Semtech datasheet unreachable on "
            "this host; see TODO(unverified) notes on the sheet. ***",
            "", V9_SX1280_PINS),
        "balloon_flight_v9:TPS7A0233": _v9_symbol(
            V9_LIBNAME, "TPS7A0233", "TPS7A02",
            "Package_TO_SOT_SMD:SOT-23-5",
            "TI TPS7A02 3.3 V ultra-low-Iq LDO (25 nA), SOT-23-5 - ADR-006 3.3 V "
            "rail. EN/NC tie-off not fixed by any record.",
            "", V9_TPS7A02_PINS),
        # A repo-local 3-pad solder-jumper symbol, deliberately NOT taken from
        # KiCad's `Jumper` library: the shared sym-lib-table is written by BOTH
        # generators, and the C3 generator's union does not carry `Jumper`.
        # Keeping the selector inside balloon_flight_v9 keeps the sheet
        # resolvable in either generation order.
        "balloon_flight_v9:F33_VCC_SEL": _v9_symbol(
            V9_LIBNAME, "F33_VCC_SEL", "F33_VCC_SEL (5V raw | 3V3)",
            "Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm",
            "ADR-029 D8 pin-1 rail selector (operator-RATIFIED 2026-10-05): a "
            "3-pad solder jumper. pin 2 COMMON -> F33_VCC; pin 1 -> VSCAP (raw "
            "supercap node, PRE-LDO) to fly the F33; pin 3 -> +3V3 (TPS7A02 OUT) "
            "to fly the nested bare LoRa2021. ADR-044 option (a) / ADR-047 2.",
            "", [("1", "A_VSCAP", "passive"), ("2", "COM", "passive"),
                 ("3", "B_3V3", "passive")]),
        # --- the HUB-SIDE wing interface (ADR-046 s2.1/s2.2/s4.1 +
        # docs/WING-TO-HUB-SOCKET-SPEC.md, implemented by ADR-048).  FOUR of these
        # sit on the v9 hub, one per edge, at 90 deg spacing; each one is the
        # socket land set that one wing tab solders onto.  Pin names are the
        # WING-side names of ADR-046 s2.1 (1 SOLAR_P, 2 GND, 3 RF_FEED, 4 SOLAR_N);
        # the hub NET of each pin is fixed per interface by the socket spec s3.
        # Pin TYPE is 'passive' on every pin on purpose: this is a hand-soldered
        # copper land set with no driver, so no ERC power/PA/RF termination is
        # asserted here.  Pin 3 (RF_FEED) is an unnetted V2 provision on v9
        # (ADR-046 s2.4) and is deliberately left with no net and no no_connect
        # flag - see OPEN-21.
        "balloon_flight_v9:WING_SOCKET_4P": _v9_symbol(
            V9_LIBNAME, "WING_SOCKET_4P", "WING_SOCKET_4P (hub wing interface)",
            "Tracker_Mechanical:Wing_Tab_4P",
            "Hub-side wing interface / socket land set for the v9 3D hub+4-wing "
            "assembly: 4 lands per face on BOTH outer layers = 8 copper lands per "
            "interface, land 4.0 x 1.2 mm, pitch 1.8 mm, insertion depth 6.0 mm, "
            "routed slot 0.9 mm +/-0.10 mm, 90 deg attach, edge clearance "
            ">= 1.0 mm (ADR-046 s2.2 over the socket spec's >= 0.5 mm - see "
            "ADR-048 D-1). Pads 1..4 = SOLAR_P / GND / RF_FEED (v9 provision, NO "
            "NET) / SOLAR_N. Geometry lives in the real footprint "
            "Tracker_Mechanical:Wing_Tab_4P; NOT human-accepted (ADR-046 + "
            "ADR-048 are Status Proposed).",
            "", [("1", "SOLAR_P", "passive"), ("2", "GND", "passive"),
                 ("3", "RF_FEED", "passive"), ("4", "SOLAR_N", "passive")]),
        # --- ADR-051 s2.1: the HUB-MOUNTED array as its OWN series string.
        # Symbol name mandated by ADR-051 s2.1.1.  The pin FUNCTIONS `P` / `N`
        # are load-bearing: scripts/bypass_diode_check.py resolves an on-board
        # cell's polarity from exactly these two function strings, and
        # scripts/hub_array_topology_check.py identifies the cell by its `PVA<n>`
        # reference.  Footprint is deliberately EMPTY: the hub outline is a
        # form-factor decision owned by another task (ADR-051 s2.3).
        "balloon_flight_v9:PVA_CELL": _v9_symbol(
            V9_LIBNAME, "PVA_CELL", "SolarCell_78x39mm",
            "balloon_flight_v9:PVA_CELL",
            "Hub-mounted solar cell of the INDEPENDENT hub array string "
            "(ADR-051 s2.1, LARGE class per ADR-049: 78.55 x 38.90 mm, 30.6 cm2, "
            "~0.5 V / ~1.2 A). Pin 1 = P (+), pin 2 = N (-). The CELL COUNT and "
            "the MOUNTING PLANE are OPEN (ADR-051 s2.2 + s4 items 3/4/5, ADR-054 "
            "s4.5) - the count on this sheet is a documented PLACEHOLDER, not a "
            "sizing decision. Footprint NOT fixed: the hub outline does not exist yet.",
            "", [("1", "P", "passive"), ("2", "N", "passive")]),
        # --- ADR-051 s2.1 decision 1: the hub string's OWN converter input.
        # A PROVISION - which part (sub-uA harvester H2/H3 vs the main converter
        # M5/M6) is unresolved (ADR-051 s4 items 3 and 5; ADR-054 s1.3).
        "balloon_flight_v9:HUB_CONVERTER": _v9_symbol(
            V9_LIBNAME, "HUB_CONVERTER", "HUB_PV input (part TODO(unverified))",
            "balloon_flight_v9:HUB_CONVERTER",
            "The hub array's OWN converter / harvester input (ADR-051 s2.1 "
            "decision 1 - the hub string is never in series with, and never a tap "
            "on, the wing chain). Pin 1 = PV_P (HUB_PV_P), pin 2 = GND (the ONE "
            "node this string may share with the wing system), pin 3 = PV_N "
            "(HUB_PV_N). The chosen part is OPEN: ADR-051 s2.2 recommends a "
            "2-cell H2 string on a sub-uA harvester (bq25570 class) but the "
            "H2/H3 vs M5/M6 fork and the harvester's peak-input rating are "
            "unresolved (ADR-051 s4 items 3/5/6, OPEN-26).",
            "", [("1", "PV_P", "passive"), ("2", "GND", "passive"),
                 ("3", "PV_N", "passive")]),
        # --- ADR-051 s2.5 decision item 5 + s2.6: one latched cut driver and
        # cut-sense channel per wing.  Both halves share the wing's RF_FEED
        # land: ONE conductor plus the shared ground return does the nichrome
        # drive AND the continuity sense.
        "balloon_flight_v9:CUT_CHANNEL": _v9_symbol(
            V9_LIBNAME, "CUT_CHANNEL",
            "latched cut driver + cut-sense (part TODO(unverified))",
            "balloon_flight_v9:CUT_CHANNEL",
            "Per-wing cutter channel provision (ADR-051 s2.5 decision item 5 + "
            "s2.6). Pin 1 = VSCAP (raw supercap node, post-BAT54, PRE-LDO, so the "
            "channel works with the converter dead - ADR-047 s2.1), pin 2 = GND, "
            "pin 3 = the wing's RF_FEED land (cut DRIVE and continuity SENSE on "
            "one conductor plus the shared ground). THE DRIVE MUST BE A LATCHED "
            "ONE-SHOT: cutting is irreversible and a level-sensitive driver can "
            "re-fire on a reset, a brown-out, a firmware retry or a floating "
            "gate (ADR-051 s2.5.1). Exact part, the sense divider and the GPIO "
            "assignment are all TODO(unverified) - see OPEN-25 and OPEN-28.",
            "", [("1", "VSCAP", "passive"), ("2", "GND", "passive"),
                 ("3", "CUT_W", "passive")]),
    }


# --- component table -------------------------------------------------------
# ref, lib_id, value, footprint, dnp, note
V9_COMPONENTS = [
    ("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1U-N8R8",
     "RF_Module:ESP32-S3-WROOM-1U", False,
     "ADR-029 D1 / ADR-037 D1: octal-PSRAM -N8R8, U.FL variant."),
    ("U2", "balloon_flight_v9:F33_2G4", "LoRa2021F33-2G4",
     "balloon_flight_v9:LoRa2021F33_2G4", False,
     "ADR-034 D1/D2: 433 MHz TX on the 2 W sub-GHz port (pin 9)."),
    ("U3", "balloon_flight_v9:LR2021_BARE", "LoRa2021_Castellated",
     "balloon_flight_v9:LoRa2021_Castellated", False,
     "ADR-034 D1: separate bare LoRa2021 = the 2.4 GHz RX chip."),
    ("U4", "balloon_flight_v9:SX1280", "SX1280",
     "balloon_flight_v9:SX1280_QFN24", False,
     "ADR-029 D2b + ADR-035: dedicated 2.4 GHz ranging radio."),
    ("U5", "RF_GPS:MAX-M10S", "MAX-M10S", "RF_GPS:ublox_MAX", False,
     "ADR-029 D2b: GNSS L1 position/time; receive-only, continuous (ADR-035 D3)."),
    ("U6", "balloon_flight_v9:MS5611_BARO", "MS5611-01BA",
     "Package_LGA:LGA-8_3x5mm_P1.25mm", False,
     "Barometer, 10-1200 hPa flight profile (ADR-029 pin plan: I2C on GPIO1/2)."),
    ("U7", "balloon_flight_v9:TPS7A0233", "TPS7A02",
     "Package_TO_SOT_SMD:SOT-23-5", False,
     "ADR-006: TPS7A02 3.3 V LDO, solar -> BAT54 -> supercap -> LDO."),
    ("C_CAP1", "Device:C_Polarized", "3.3F 2.7V (AVX SCC)",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", False,
     "ADR-006: 2x 3.3 F 2.7 V in series = 1.65 F @ 5.4 V (cell A)."),
    ("C_CAP2", "Device:C_Polarized", "3.3F 2.7V (AVX SCC)",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", False,
     "ADR-006: supercap bank (cell B). Sized to ONE burst (ADR-036)."),
    ("D1", "Device:D_Schottky", "BAT54", "Diode_SMD:D_SOD-123", False,
     "ADR-006: solar reverse-current Schottky (blocks back-feed into the "
     "solar cells at night)."),
    ("R_DIV1", "Device:R", "1M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-006: 2x 1 MOhm supercap-rail ADC divider (upper)."),
    ("R_DIV2", "Device:R", "1M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-006: 2x 1 MOhm supercap-rail ADC divider (lower)."),
    ("R_F1", "Device:R", "100R", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-029 D2(d): dedicated RC/ferrite feed (100 Ohm + 10 uF) into the GNSS "
     "rail."),
    ("C4", "Device:C", "10uF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-029 D2(d): GNSS-rail bulk cap on the filtered feed."),
    ("ANT1", "Connector:Conn_Coaxial", "U.FL_433_TX",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-029 D3 (sub-GHz U.FL) + ADR-034 D1: 433 MHz TX feed = F33 pin 9."),
    ("ANT2", "Connector:Conn_Coaxial", "U.FL_2G4_RANGE",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-108 Revision R1 (2026-10-07): the SX1280 2.4 GHz RANGING feed. "
     "Re-pointed from the F33 ANT-2G4 port because ADR-034 D1/D5 state the "
     "F33 carries TX ONLY (its pin 9 sub-GHz port is the 433 MHz TX) while "
     "the SX1280 - operator-ratified (ADR-029 D2b) and given its own TDM "
     "slot (ADR-035) - needs a feed; there are four U.FL sites and four RF "
     "parts (ADR-034 D5). Hub-side wire dipole per ADR-009. See OPEN-2."),
    ("ANT3", "Connector:Conn_Coaxial", "U.FL_2G4_RX",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-034 D1: 2.4 GHz RX feed of the bare LoRa2021 (pin 10, the Site-B "
     "2.4 GHz RX). ADR-108 Revision R1: the four-feed / five-feed conflict "
     "is SETTLED - ANT3 keeps its role and ANT2 moves to the SX1280, so the "
     "two 2.4 GHz-capable feeds (ANT2 ranging, ANT3 link RX) stay separate "
     "as ADR-029 D3 requires. Hub-side wire dipole per ADR-009."),
    ("ANT4", "Connector:Conn_Coaxial", "U.FL_GNSS_L1",
     "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical", False,
     "ADR-029 D3: GNSS L1 feed, +Y sky-facing edge."),
    # --- ADR-047: the F33 5 V PA rail provision (operator directive 2026-10-07) ---
    ("J_VCC", "balloon_flight_v9:F33_VCC_SEL", "F33_VCC_SEL (5V raw | 3V3)",
     "Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm", False,
     "ADR-029 D8 (operator-RATIFIED 2026-10-05): the mandatory SELECTABLE pin-1 "
     "rail (3-pad solder jumper). pin 2 = COM -> F33_VCC; pin 1 = VSCAP (raw "
     "supercap node, PRE-LDO) for the F33; pin 3 = +3V3 (TPS7A02 OUT) for the "
     "nested bare LoRa2021. ADR-044 option (a) + ADR-047 2. Rendered with a "
     "repo-local symbol so no new symbol library is required."),
    ("C_BULK", "Device:C", "100uF",
     "Capacitor_SMD:C_1206_3216Metric", False,
     "ADR-047 4: local bulk cap AT THE MODULE PIN, sized for the current step "
     "(holds 1.2 A within 20 mV for 1.67 us). Cited: "
     "docs/PCB-HANDOVER-FOR-JLCPCB.md 2.4 '>=100 uF low-ESR tantalum or ceramic at "
     "PA VCC'; ADR-029 2(f) 'each radio rail gets its own ferrite + bulk cap'."),
    ("C_HF", "Device:C", "100nF",
     "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-047 4: HF bypass at the module pin. Same citation as C_BULK "
     "('... plus 100 nF HF bypass')."),
    ("D_CLAMP", "Device:D_TVS", "TVS clamp (set point TODO(unverified))",
     "Diode_SMD:D_SOD-323", False,
     "ADR-044 option (c) + ADR-047 7: over-voltage INSURANCE on F33_VCC, made "
     "required by the operator's over-provisioning directive. The set point must "
     "sit above the 5.4 V rail top and below the F33's damage threshold, which "
     "Rev 1.1 of the datasheet does not publish -> part AND set point are "
     "TODO(unverified). See OPEN-16."),
    ("R_MON1", "Device:R", "4.7M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-047 6: F33 rail-monitor divider (upper). 4.7 M keeps the lead at "
     "0.574 uA / 3.1 uW so the divider pair does not eat ADR-036's 100 uW night "
     "anchor (the pre-existing 1M/1M SCAP divider already draws 14.6 uW)."),
    ("R_MON2", "Device:R", "4.7M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-047 6: F33 rail-monitor divider (lower). Ratio 0.5 -> 5.4 V reads "
     "2.70 V at the ESP32-S3 ADC."),
    ("C_MON", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-047 6: ADC sample-and-hold reservoir for the 2.35 MOhm-Thevenin "
     "monitor tap (tau = 23.5 ms). Without it the S/H cap cannot settle."),
    ("R_BAL1", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-006 / ADR-044 'already fixed': 2x 10 kOhm supercap balancing resistors "
     "(upper cell). Mandated by the Accepted ADR-006 and restated in ADR-044; "
     "they were missing from this sheet."),
    ("R_BAL2", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-006 / ADR-044: balancing resistor, lower cell."),
    # --- ADR-046 / WING-TO-HUB-SOCKET-SPEC / ADR-048: the FOUR wing-mount
    # interfaces.  One hub edge each, at 90 deg spacing.  Every pad count, net
    # name and net assignment is cited in the component note; the physical land
    # geometry lives in the real footprint Tracker_Mechanical:Wing_Tab_4P, not in
    # a generic pin header.
    ("J_W1", "balloon_flight_v9:WING_SOCKET_4P", "WING_SOCKET_4P (hub wing interface 1)",
     "Tracker_Mechanical:Wing_Tab_4P", False,
     "ADR-046 s1/s2 + socket spec s1: wing interface 1 of 4. 4 lands per face x 2 "
     "faces = 8 lands, pad order 1 SOLAR_P / 2 GND / 3 RF_FEED(v9 provision, no "
     "net) / 4 SOLAR_N. Net assignment (socket spec s3.1): pad 1 = stack TOP "
     "W1_SOLAR_P -> BAT54; pad 2 = GND; pad 4 = W1_SOLAR_N, linked to wing 2's "
     "W2_SOLAR_P on the hub. Land 4.0 x 1.2 mm, pitch 1.8 mm, insertion 6.0 mm "
     "(ADR-046 s2.2/s4.1)."),
    ("J_W2", "balloon_flight_v9:WING_SOCKET_4P", "WING_SOCKET_4P (hub wing interface 2)",
     "Tracker_Mechanical:Wing_Tab_4P", False,
     "ADR-046 s1/s2 + socket spec s1: wing interface 2 of 4. Same 8-land socket. "
     "pad 2 = GND; pad 4 = W2_SOLAR_N linked to wing 3's W3_SOLAR_P; pad 1 lands "
     "on the W1_SOLAR_N / W2_SOLAR_P hub-link node (socket spec s3.1)."),
    ("J_W3", "balloon_flight_v9:WING_SOCKET_4P", "WING_SOCKET_4P (hub wing interface 3)",
     "Tracker_Mechanical:Wing_Tab_4P", False,
     "ADR-046 s1/s2 + socket spec s1: wing interface 3 of 4. Same 8-land socket. "
     "pad 2 = GND; pad 4 = W3_SOLAR_N linked to wing 4's W4_SOLAR_P; pad 1 lands "
     "on the W2_SOLAR_N / W3_SOLAR_P hub-link node (socket spec s3.1)."),
    ("J_W4", "balloon_flight_v9:WING_SOCKET_4P", "WING_SOCKET_4P (hub wing interface 4)",
     "Tracker_Mechanical:Wing_Tab_4P", False,
     "ADR-046 s1/s2 + socket spec s1: wing interface 4 of 4. Same 8-land socket. "
     "pad 2 = GND; pad 4 = W4_SOLAR_N = the stack BOTTOM, tied to the hub GND "
     "plane (ADR-046 s2.3: 'stack_bot = W4.SOLAR_N -> system GND'); DO NOT tie "
     "any other W<n>_SOLAR_N to GND (socket spec s3). pad 1 lands on the "
     "W3_SOLAR_N / W4_SOLAR_P hub-link node (socket spec s3.1)."),
    # --- ADR-051 s2.7 / ADR-053 s2.2 (as amended by ADR-054 s3.2): the four
    # HUB-SIDE per-interface bypass diodes.  POPULATED (not DNP) and re-rated:
    # a cutter-carrying flight needs them, and the DNP BAT54 the socket spec
    # named is disqualified twice over.
    #   1. WHY HUB-SIDE.  A cut jettisons the wing AND every part soldered to
    #      it, so a wing-board diode leaves with the wing and cannot bridge the
    #      gap it was fitted to bridge (ADR-054 s2.2, adversarial F3).  Only a
    #      hub-side, per-interface diode can restore the broken PATH.  Without
    #      it a cutter flight is WORSE than baseline: the first cut opens the
    #      string and the array delivers 0.00 W.
    #   2. WHY >= 2 A / 40 V AND NOT THE 200 mA BAT54.  Post-cut the other wings
    #      drive the array's FULL 1.2 A continuously through this diode for the
    #      rest of the flight - a PERMANENT CONTINUOUS bypass duty, not the
    #      shading transient a 200 mA part is sold as (ADR-051 s2.4 decisions
    #      4.2/4.3, s2.7); and the reverse rating must clear the ~9.58 V cold
    #      open-circuit stack against a 30 V part (ADR-050 s3.2).  SS24 = 2 A /
    #      40 V, in the class ADR-051 s2.7 names ("SS24 or PMEG4020ER class").
    #   3. WHY THE PACKAGE MOVES.  SOD-323 cannot carry 2 A (ADR-051 s2.7), so
    #      the land pattern moves to SMA.  See OPEN-11 for the delta = 1 derate
    #      still owed and OPEN-28 for the hub re-layout this forces.
    ("D_BP1", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-051 s2.7 + ADR-054 s2.2/s3.2 (HUB-SIDE placement): bypass Schottky "
     "ACROSS wing interface 1 - cathode to W1_SOLAR_P, anode to W1_SOLAR_N. "
     "POPULATED (ADR-051 s2.4 decision 4.2 supersedes the DNP instruction of "
     "ADR-046 s6 / socket spec s5 for any cutter-carrying flight). SS24 = 2 A / "
     "40 V: the post-cut bypass path is a PERMANENT CONTINUOUS 1.2 A path, and "
     "the 200 mA / 30 V BAT54 is disqualified against it. SMA land, not SOD-323: "
     "SOD-323 cannot carry 2 A."),
    ("D_BP2", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-051 s2.7 + ADR-054 s2.2: bypass Schottky across wing interface 2 - "
     "cathode to W2_SOLAR_P (= the W1_SOLAR_N hub link), anode to W2_SOLAR_N. "
     "POPULATED, SS24 (2 A / 40 V). Same hub-side rationale as D_BP1."),
    ("D_BP3", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-051 s2.7 + ADR-054 s2.2: bypass Schottky across wing interface 3 - "
     "cathode to W3_SOLAR_P (= the W2_SOLAR_N hub link), anode to W3_SOLAR_N. "
     "POPULATED, SS24 (2 A / 40 V). Same hub-side rationale as D_BP1."),
    ("D_BP4", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-051 s2.7 + ADR-054 s2.2: bypass Schottky across wing interface 4 - "
     "cathode to W4_SOLAR_P (= the W3_SOLAR_N hub link), anode to W4_SOLAR_N = "
     "GND. POPULATED, SS24 (2 A / 40 V). Same hub-side rationale as D_BP1. This "
     "is the only one whose anode sits on GND, because wing 4's SOLAR_N IS the "
     "stack bottom (ADR-046 s2.3)."),
    # --- ADR-058: THE LR2021 ON-CHIP NTC TEMPERATURE-COMPENSATION PROVISION.
    # The LR2021 silicon contains the XTAL compensation engine; it needs only an
    # external NTC thermistor + bias resistor at the crystal (Semtech DS 2.2
    # s1.9.2 "Figure 1-15: NTC Connection"; SetTempCompCfg opcode 0x0132 and
    # SetNtcParams opcode 0x0133 per Tables 6-69/6-70; chip pin 3 = NTC, chip
    # pin 6 = VTCXO/VNTC per Table 2-1).  Both parts are DNP, with the reason
    # recorded in the net note and OPEN-29: on the OWNED bare NiceRF module the
    # chip's NTC sense pin has NO castellation (the vendor pin table
    # docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf s7 enumerates all 18
    # pads and the only oscillator pad is 13 = VTCXO), so the sense node has no
    # path back to the chip and the loop cannot be closed.  The land is provided
    # now because there is no v9 hub PCB yet, so it costs no respin: a module (or
    # revision) that breaks the pin out closes the loop at zero cost.  Values are
    # TODO(unverified) because they must be characterised from the populated part
    # (ADR-058 D4), not guessed.
    ("R_NTC1", "Device:R", "TODO(unverified) (sets ntc_r_ratio)",
     "Resistor_SMD:R_0402_1005Metric", True,
     "ADR-058 D1/D4: series/bias resistor of the on-chip NTC temperature-"
     "compensation divider, from the VTCXO/VNTC bias rail to the NTC sense node. "
     "Its value must be characterised against the populated NTC (it sets "
     "SetNtcParams ntc_r_ratio = RBiasRatio, 'the ratio between the resistor bias "
     "value and the NTC resistor value at 25 degC, 10 bits with 9 fractional bits "
     "(10,9)' - DS 2.2 Table 6-70) -> TODO(unverified). DNP, not populated: the "
     "sense node has no path back to the chip on the owned bare module (OPEN-29, "
     "ADR-058 D6)."),
    ("TH_NTC1", "Device:Thermistor_NTC", "TODO(unverified) (NTC, R25/beta TODO)",
     "Resistor_SMD:R_0402_1005Metric", True,
     "ADR-058 D1/D3/D4: the NTC thermistor of the on-chip temperature-"
     "compensation provision - sense node to GND. SITING RULE (ADR-058 D3): it "
     "must be thermally coupled to the radio's XTAL, NOT parked on the far side "
     "of the board, and NOT sited where a self-heating neighbour dominates its "
     "reading (the F33 2 W PA, the hub converter). Part, R25 and beta are "
     "TODO(unverified): they must be read from the chosen part's datasheet and "
     "matched to ntc_beta (DS 2.2 Table 6-70: 'NTC temperature in 2 Kelvin/lsb') "
     "and to the -60 degC design case - see OPEN-30.  0402 land because an 0402 "
     "NTC uses the same land as an 0402 resistor. DNP (OPEN-29, ADR-058 D6)."),
]

# --- ADR-051 §2.1: the hub array.  Its cell count is a PARAMETER, not a
# decision.  *** THE COUNT BELOW IS A DOCUMENTED PLACEHOLDER *** ADR-051 §2.2
# recommends H2 = 2 LARGE cells (H3 = 3 is the fallback); the count, the
# MOUNTING PLANE and the harvester part are all OPEN (ADR-051 §4 items 3/4/5/6;
# ADR-054 §4.5), and the hub OUTLINE is a form-factor decision owned by another
# task (ADR-051 §2.3) - which is why the cells' footprint field is left EMPTY.
# Changing this one number regenerates the cells, the HUB_PV_MID<n> interiors,
# the per-cell hub bypass diodes and the whole hub string.  Nothing else in this
# file hard-codes the hub cell count.
V9_HUB_ARRAY_CELLS = 2

for _i in range(1, V9_HUB_ARRAY_CELLS + 1):
    V9_COMPONENTS.append(
        ("PVA%d" % _i, "balloon_flight_v9:PVA_CELL", "SolarCell_78x39mm",
         "", False,
         "Cell %d of the INDEPENDENT hub-array string (ADR-051 §2.1, LARGE "
         "class per ADR-049: 78.55 x 38.90 mm, 30.6 cm2, ~0.5 V / ~1.2 A). The "
         "string is its OWN series string with its OWN converter input; it is "
         "NEVER in series with, and never a tap on, the wing chain - the only "
         "node it may share with the wing system is GND. Enforced by "
         "scripts/hub_array_topology_check.py. CELL COUNT / MOUNTING PLANE / "
         "OUTLINE ARE OPEN (OPEN-26); this ref is a PLACEHOLDER." % _i))
    V9_COMPONENTS.append(
        ("D_HUB%d" % _i, "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
         "Bypass Schottky across hub-array cell PVA%d: cathode to the cell's + "
         "node, anode to its - node. ADR-051 §2.2 places the hub cells on the "
         "hub and says they 'need their own diodes'; ADR-053 §1.6/§2.4 keeps "
         "per-GROUP over per-CELL as the general rule, and ADR-054 §4.5 leaves "
         "the hub's OWN granularity explicitly OPEN (OPEN-27). Populated at the "
         "same >=2 A / 40 V class as the per-interface diodes (SS24) so a hub "
         "cell failure is contained BY A PATH that survives any wing cut." % _i))

V9_COMPONENTS.append(
    ("U_HUB_CVT", "balloon_flight_v9:HUB_CONVERTER",
     "HUB_PV input (part TODO(unverified))", "", False,
     "The hub array's OWN converter / harvester input provision (ADR-051 §2.1 "
     "decision 1: 'its positive terminal feeds its own converter/harvester "
     "input, on its own net'). Pin 1 = HUB_PV_P, pin 2 = GND (the ONE shared "
     "node), pin 3 = HUB_PV_N. The PART is unresolved: ADR-051 §2.2 recommends "
     "the 2-cell H2 string on a sub-uA harvester of the bq25570 class, but the "
     "H2/H3 vs M5/M6 fork and the harvester's peak-input-power rating against "
     "the array's face-on peak are OPEN (OPEN-26; ADR-051 §4 items 3/5/6)."))

for _i in range(1, 5):
    V9_COMPONENTS.append(
        ("U_CUT%d" % _i, "balloon_flight_v9:CUT_CHANNEL",
         "latched cut driver + cut-sense (part TODO(unverified))", "", False,
         "Wing %d cut channel (ADR-051 §2.5 decision item 5 + §2.6): the "
         "nichrome cutter drive AND the cut-sense continuity line on the wing's "
         "ONE reserved RF_FEED conductor plus the shared ground. Pin 1 = VSCAP "
         "(raw supercap node, post-BAT54, PRE-LDO, so the cut works with the "
         "converter dead - ADR-047 §2.1); pin 2 = GND; pin 3 drives/senses "
         "CUT_SENSE_W%d = J_W%d pad 3 (RF_FEED). THE DRIVE IS MANDATED TO BE A "
         "LATCHED ONE-SHOT (ADR-051 §2.5.1): cutting is irreversible, and a "
         "level-sensitive driver can re-fire on a reset, brown-out, retry or "
         "floating gate - each fire costing ~2.59 J of the bank\'s 16.63 J at "
         "the moment the bank matters. Firmware must also serialise cuts "
         "(4 simultaneous fires = 9.9 A = 2.4x the IRLML2502 class rating) and "
         "log a silently-failed cut below the ~3.3 V arming threshold. Part, "
         "sense divider, GPIO and the latch's exact topology: TODO(unverified) "
         "- OPEN-25 and OPEN-28." % (_i, _i, _i)))


# --- nets ------------------------------------------------------------------
# net -> [(ref, pin), ...].  Each entry carries its citation.
V9_NETS = [
    ("+3V3", [("U1", "2"), ("U2", "5"), ("U3", "1"), ("U5", "6"), ("U5", "7"),
              ("U5", "9"), ("U6", "1"), ("U6", "4"), ("U7", "5"), ("R_F1", "1"),
              ("U4", "15"), ("J_VCC", "3")],
     "ADR-006 3.3 V rail (TPS7A02 OUT); U2 pin 5 CE strapped to 3V3 per the "
     "ADR-029 pin plan (blocker 3: confirm CE vs the purchased revision). "
     "U5 pins 6/7/9 (V_BCKP / VCC_IO / ~RESET) are tied to +3V3 on the precedent "
     "of the frozen v8i board, which uses the SAME ublox_MAX footprint and "
     "RF_GPS:MAX-M10S symbol (v8i_krt_gnss.kicad_pcb U3 pads 6,7,8,9 = +3V3; "
     "the v8i board is sha256-pinned in this generator). J_VCC pin 3 is the "
     "3.3 V position of the ADR-029 D8 pin-1 selector (nested bare LoRa2021). "
     "R_F1 pin 1 feeds the GNSS RC filter per ADR-029 2(d). "
     "ADR-108 Revision R1 (2026-10-07) CLOSED OPEN-1 as 'U4 pins 1/2 are on "
     "+3V3'.  THE PINOUT REVISION OF 2026-10-15 SUPERSEDES THE PIN NUMBERS IN "
     "THAT RULING: on the REAL part the radio supply is pin 15 (VBAT), and pins "
     "1 and 2 are VR_PA (a regulator OUTPUT, bypassed by C5 to GND) and VDD_IN "
     "(the internal regulator's output node, tied to pin 12 DCC_FB through L4) "
     "-- NEITHER may sit on a rail.  So the rail of record is unchanged (the "
     "3.3 V rail IS the SX1280 supply of "
     "record - ADR-047 2.3 states verbatim that the 3.3 V rail also carries "
     "the ESP32-S3, the SX1280 and the GNSS, and docs/POWER-BUDGET-V9-D2BE.md "
     "2 puts BOTH SX1280 states (ranging TX 70 mA, ranging RX 15 mA) on the "
     "3.3 V rail. ADR-060 s4 confirms the SX1280 default is no TCXO and NO "
     "new or gated rail, so no rail is created for this part. The ADR-029 "
     "2(f) provision (its own ferrite + bulk cap) is NOT yet fitted and is "
     "registered as OPEN-33. "
     "OPEN-7 CLOSURE (2026-10-07): U6 pin 4 (CSB) is tied to +3V3 on the "
     "precedent of the frozen v8j MS5611 board "
     "(tracker/hardware/output/v8j_krt_ms5611.kicad_pcb), which carries the "
     "SAME Package_LGA:LGA-8_3x5mm_P1.25mm barometer footprint in the SAME "
     "I2C mode (its pads 7/8 are I2C_SDA / I2C_SCL, exactly this sheet U6 "
     "pins 7/8) and ties pad 4 = +3V3, pad 2 = GND, pad 6 = GND."),
    ("GND", [("U1", "1"),
             ("U2", "2"), ("U2", "3"), ("U2", "4"), ("U2", "6"), ("U2", "7"),
             ("U2", "8"), ("U2", "11"),
             ("U3", "2"), ("U3", "8"), ("U3", "11"), ("U3", "12"), ("U3", "18"),
             # U4's REAL ground pads: 0 is the exposed pad (whose connectable end lands at the
             # symbol origin), 5/13/20/21/23/24 are the GND pins.  The placeholder list (3/15..25)
             # was the 13/12 half-split numbering and would now short the SPI pins to ground.
             ("U4", "0"), ("U4", "5"), ("U4", "13"), ("U4", "20"), ("U4", "21"),
             ("U4", "23"), ("U4", "24"),
             ("U5", "1"), ("U6", "2"), ("U6", "3"), ("U6", "6"), ("U7", "2"), ("C_CAP2", "2"),
             ("R_DIV2", "2"), ("C4", "2"), ("R_BAL2", "2"),
             ("C_BULK", "2"), ("C_HF", "2"), ("D_CLAMP", "2"), ("R_MON2", "2"),
             ("C_MON", "2"),
             ("ANT1", "2"), ("ANT2", "2"), ("ANT3", "2"), ("ANT4", "2"),
             ("J_W1", "2"), ("J_W2", "2"), ("J_W3", "2"), ("J_W4", "2"),
             ("J_W4", "4"), ("D_BP4", "2"), ("TH_NTC1", "2")],
     "Ground. F33 GND pads 2,3,4,6,7,8,11; bare GND pads 2,8,11,12,18 "
     "(docs/DUAL-VARIANT-DESIGN.md). J_W1..J_W4 pin 2 are the four wing "
     "interfaces' GND lands: socket spec s3 makes each interface's GND land tie "
     "DIRECTLY to the hub ground plane and warns 'Do not tie any W<n>_SOLAR_N to "
     "GND except W4_SOLAR_N'. J_W4 pin 4 and D_BP4 pin 2 are that single "
     "exception: wing 4's SOLAR_N IS the 6.0 V stack bottom (ADR-046 s2.3 "
     "'stack_bot = W4.SOLAR_N -> system GND'). Wings 1-3 SOLAR_N are on the "
     "W1_SOLAR_N / W2_SOLAR_N / W3_SOLAR_N hub links, NOT here. "
     "OPEN-7 CLOSURE (2026-10-07): U6 pin 2 (PS) and U6 pin 6 (SDO) are "
     "tied to GND on the precedent of the frozen v8j MS5611 board "
     "(tracker/hardware/output/v8j_krt_ms5611.kicad_pcb) - the SAME "
     "Package_LGA:LGA-8_3x5mm_P1.25mm footprint, same I2C mode - which ties "
     "its pad 2 and pad 6 to GND."),
    ("VSCAP", [("D1", "1"), ("C_CAP1", "1"), ("U7", "1"), ("U7", "3"),
               ("R_DIV1", "1"), ("R_BAL1", "1"), ("J_VCC", "1")],
     "ADR-006 chain: BAT54 cathode -> supercap bank (top) -> TPS7A02 IN ->, for "
     "the F33, the pin-1 selector's raw, PRE-LDO position. U7 pin 3 (EN) sits on "
     "this net beside U7 pin 1 (IN) so the LDO is permanently on - decided by "
     "docs/coordination/SCHEMATIC-PLAN-3VARIANTS.md 5 item 4 and 6 items 7/14 "
     "('U3.EN tied to U3.VIN on the VBAT net'), and by the v8i board "
     "(U4 pad 3 = VCAP = pad 1)."),
    ("SCAP_MID", [("C_CAP1", "2"), ("C_CAP2", "1"), ("R_BAL1", "2"),
                  ("R_BAL2", "1")],
     "ADR-006 (Accepted): the SERIES mid-node of the 2x 3.3 F 2.7 V bank "
     "(1.65 F @ 5.4 V). This net was MISSING from the sheet: its absence put "
     "C_CAP2 straight across the rail (a 2.7 V-rated cap on a 5.4 V node) and "
     "left C_CAP1 pin 2 floating. R_BAL1/R_BAL2 (2x 10 kOhm, ADR-006) balance "
     "the two cells here."),
    ("W1_SOLAR_P", [("J_W1", "1"), ("D1", "2"), ("D_BP1", "1")],
     "ADR-046 s2.3 / socket spec s3.1: stack TOP = wing 1's solar POSITIVE "
     "terminal (W1_SOLAR_P) -> BAT54 (D1) -> supercap bank (ADR-006). This net "
     "carries the socket spec's W1_SOLAR_P LAND of wing interface 1; it is the "
     "v9 sheet's former 1-pad `SOLAR_IN` net (which had only the D1 anode end and "
     "was filed as OPEN-12 'solar input connector not in the component list'). "
     "It is now the whole 4-wing array input: the four wing interfaces ARE the "
     "solar source, so OPEN-12 is closed by ADR-048. It is renamed from SOLAR_IN "
     "to W1_SOLAR_P because that is the land net name the socket spec s3 fixes. "
     "D_BP1 pin 1 is its cathode: the bypass Schottky's cathode goes to the "
     "wing's SOLAR_P (ADR-046 s2.3)."),
    ("W1_SOLAR_N", [("J_W1", "4"), ("J_W2", "1"), ("D_BP1", "2"), ("D_BP2", "1")],
     "ADR-046 s2.3 / socket spec s3.1: the first HUB LINK. ADR-046 s2.3 mandates "
     "`W1.SOLAR_N == W2.SOLAR_P (hub link)`, so this is ONE electrical node: it "
     "carries wing interface 1's SOLAR_N land (socket spec net name "
     "`W1_SOLAR_N`) AND wing interface 2's SOLAR_P land (socket spec net name "
     "`W2_SOLAR_P`). The node is named after the first of the pair; the "
     "land-to-node mapping for all 8 spec land names is tabulated in "
     "docs/adr/048-v9-hub-wing-interfaces.md. D_BP1 pin 2 (anode) and D_BP2 pin "
     "1 (cathode) sit across wings 1 and 2 respectively (socket spec s5)."),
    ("W2_SOLAR_N", [("J_W2", "4"), ("J_W3", "1"), ("D_BP2", "2"), ("D_BP3", "1")],
     "ADR-046 s2.3 / socket spec s3.1: the second HUB LINK - `W2.SOLAR_N == "
     "W3.SOLAR_P` is one electrical node carrying wing interface 2's SOLAR_N "
     "land and wing interface 3's SOLAR_P land (socket spec land net names "
     "W2_SOLAR_N and W3_SOLAR_P). D_BP2 anode / D_BP3 cathode."),
    ("W3_SOLAR_N", [("J_W3", "4"), ("J_W4", "1"), ("D_BP3", "2"), ("D_BP4", "1")],
     "ADR-046 s2.3 / socket spec s3.1: the third HUB LINK - `W3.SOLAR_N == "
     "W4.SOLAR_P` is one electrical node carrying wing interface 3's SOLAR_N "
     "land and wing interface 4's SOLAR_P land (socket spec land net names "
     "W3_SOLAR_N and W4_SOLAR_P). D_BP3 anode / D_BP4 cathode."),
    ("F33_VCC", [("J_VCC", "2"), ("U2", "1"), ("C_BULK", "1"), ("C_HF", "1"),
                 ("D_CLAMP", "1"), ("R_MON1", "1")],
     "ADR-044 option (a) + ADR-047 2: the F33's pin 1 VCC. Fed from the RAW "
     "supercap node PRE-LDO through the ADR-029 D8 pin-1 selector. It must NEVER "
     "be fed through the TPS7A02: that LDO is rated <=300 mA (ADR-006) / 200 mA "
     "(KiCad Regulator_Linear:TPS7A0533PDBV) against the F33's 1118 mA - a "
     "3.7x-5.6x overload and a hard failure, not a hypothesis (ADR-047 2.3)."),
    ("F33_VSENSE", [("R_MON1", "2"), ("R_MON2", "1"), ("C_MON", "1"),
                    ("U1", "21")],
     "ADR-047 6: F33 rail monitor. Divider ratio 0.5 (4.7 M / 4.7 M) -> "
     "5.4 V reads 2.70 V at ESP32-S3 IO13 (U1 pin 21). Firmware must inhibit TX "
     "below the LOADED-rail threshold for the wanted output power: >=5.0 V for "
     "the full 33.0 dBm, and >=3.54 V (interpolated) + the bank\'s ESR step for "
     "+30 dBm. See OPEN-17 for the ADC-channel TODO."),
    ("GNSS_VCC", [("R_F1", "2"), ("C4", "1"), ("U5", "8")],
     "ADR-029 2(d): the FILTERED GNSS rail - 'a dedicated RC/ferrite feed (e.g. "
     "100 Ohm + 10 uF) from 3V3 into the GNSS rail'. The MAX-M10S is a 3.3 V "
     "part, so this net must NOT hang off the 5.4 V cap node; R_F1.1 is on "
     "+3V3. Fixes a sheet defect in which R_F1.1 appeared in BOTH the +3V3 and "
     "VSCAP net lists and R_F1 pin 2 was floating."),
    ("F33_SCK", [("U1", "4"), ("U2", "12"), ("U3", "5")],
     "SPI2 FSPI SCK on GPIO4; the bare module shares SPI2 data/clock "
     "(V9-RADIO-SITE-MATRIX 3.1)."),
    ("F33_MOSI", [("U1", "5"), ("U2", "15"), ("U3", "4")],
     "SPI2 MOSI on GPIO5 (shared, see 3.1)."),
    ("F33_MISO", [("U1", "6"), ("U2", "16"), ("U3", "3")],
     "SPI2 MISO on GPIO6 (SHARED bus - see 3.1). Both slave MISO pins are typed "
     "tri_state because an SPI slave only drives MISO while its own CS is "
     "asserted; the shared data/clock bus is the landed decision in "
     "docs/V9-RADIO-SITE-MATRIX.md 3.1 ('{HP+LP} ... +4 GPIO (shared bus) ... "
     "share SPI data/clock', citing docs/V9-DUAL-LR-DESIGN-MEMO.md 5). Typing "
     "them 'output' (as they were) produced a false pin_to_pin ERC error; the "
     "pin TYPE is corrected here, no connectivity is changed."),
    ("F33_CS_N", [("U1", "7"), ("U2", "13")],
     "F33 NSS on GPIO7 (ADR-029 pin plan, unique CS)."),
    ("F33_BUSY", [("U1", "12"), ("U2", "14")],
     "F33 BUSY polled by GPIO8 (ADR-029 D4 hardware BUSY binding)."),
    ("F33_IRQ", [("U1", "17"), ("U2", "18")],
     "F33 IRQ/DIO1 on GPIO9 (ADR-029 pin plan)."),
    ("F33_RESET_N", [("U1", "18"), ("U2", "17")],
     "F33 RESET on GPIO10 (ADR-029 pin plan)."),
    # U4's pin numbers below are the REAL SX1280 pad numbers (Table 2-1).  They were 4/5/6/7/8/
    # 9/10/11/12 in the placeholder table, and the numbers moved with the pinout: leaving them
    # would re-create the 7 dead connections this card removes (CS_N driving NRESET, MOSI driving
    # XTA, DIO1 shorted to GND, ...).  SX1280_ANT_SW is GONE: the real part has no ANT_SW pin
    # (removed from the sheet in commit 96d219b3, operator-confirmed).
    ("SX1280_SCK", [("U1", "22"), ("U4", "18")],
     "SPI3 clock on GPIO14 (ADR-029 pin plan). U4 pad 18 = SCK_RTSN (real pinout)."),
    ("SX1280_MOSI", [("U1", "8"), ("U4", "17")],
     "SPI3 MOSI on GPIO15 (ADR-029 pin plan). U4 pad 17 = MOSI_RX."),
    ("SX1280_MISO", [("U1", "9"), ("U4", "16")],
     "SPI3 MISO on GPIO16 (ADR-029 pin plan). U4 pad 16 = MISO_TX."),
    ("SX1280_CS_N", [("U1", "10"), ("U4", "19")],
     "SPI3 CS on GPIO17 (ADR-029 pin plan). U4 pad 19 = NSS_CTS."),
    ("SX1280_BUSY", [("U1", "31"), ("U4", "7")],
     "SX1280 BUSY on GPIO38 (ADR-029 pin plan). U4 pad 7 = BUSY."),
    ("SX1280_RESET_N", [("U1", "32"), ("U4", "3")],
     "SX1280 RESET on GPIO39 - native JTAG MTCK lost (ADR-029 pin plan, "
     "explicit trade-off). U4 pad 3 = NRESET."),
    ("SX1280_DIO1", [("U1", "33"), ("U4", "8")],
     "SX1280 DIO1/IRQ on GPIO40 - native MTDO/JTAG lost (pin plan). U4 pad 8 = DIO1."),
    ("SX1280_DIO2", [("U1", "11"), ("U4", "9")],
     "SX1280 DIO2 on GPIO18 (pin plan, optional function). U4 pad 9 = DIO2."),
    ("SX1280_DIO3", [("U1", "34"), ("U4", "10")],
     "SX1280 DIO3 on GPIO41 - native MTDI/JTAG lost (pin plan). U4 pad 10 = DIO3."),
    ("GNSS_PPS", [("U1", "23"), ("U5", "4")],
     "MAX-M10S TIMEPULSE/PPS on GPIO21 (ADR-029 pin plan)."),
    ("GNSS_TX", [("U1", "36"), ("U5", "2")],
     "MAX-M10S TXD -> S3 RXD0/GPIO43 (pin plan; console mux is a firmware "
     "policy)."),
    ("GNSS_RX", [("U1", "37"), ("U5", "3")],
     "MAX-M10S RXD <- S3 TXD0/GPIO44 (pin plan)."),
    ("I2C_SDA", [("U1", "39"), ("U6", "7")],
     "MS5611 SDI/SDA on GPIO1, external pull-up to 3V3 required (pin plan)."),
    ("I2C_SCL", [("U1", "38"), ("U6", "8")],
     "MS5611 SCLK/SCL on GPIO2, external pull-up to 3V3 required (pin plan)."),
    ("SCAP_ADC", [("R_DIV1", "2"), ("R_DIV2", "1")],
     "ADR-006 supercap ADC divider tap. The ADC GPIO is UNRESOLVED: ADR-006 "
     "says GPIO0, the ADR-029 pin plan reserves IO0 as a boot strap."),
    ("ANT1_433_TX", [("U2", "9"), ("ANT1", "1")],
     "ADR-034 D1/D2 + ADR-029 D3: 433 MHz TX, F33 sub-GHz ANT."),
    ("ANT2_2G4_RANGE", [("U4", "22"), ("ANT2", "1")],
     "ADR-108 Revision R1 (2026-10-07) CLOSES OPEN-2. ANT2 is re-pointed "
     "from the F33 2.4 GHz port to the SX1280 RFIO. ADR-029 D2b/D3 "
     "enumerated FOUR connectors (GNSS L1, F33 sub-GHz, F33 ANT-2G4, "
     "SX1280); ADR-034 D1/D5 then re-pointed the 2.4 GHz link RX at a "
     "SEPARATE bare LoRa2021 and states plainly that the F33 carries TX "
     "ONLY. So of the five candidate feeds exactly one has no role - the "
     "F33 ANT-2G4 port - and the SX1280, an operator-RATIFIED radio "
     "(ADR-029 D2b, 2026-10-05) that the TDM schedule gives its own slot "
     "(ADR-035), needs a feed. One U.FL site is the only currency "
     "available, so ANT2 serves the SX1280 and U2 pin 10 becomes an "
     "explicit no-connect. The count is settled at FOUR feeds for the FOUR "
     "RF parts of ADR-034 D5 (433 TX, 2.4 ranging, 2.4 RX, GNSS L1) "
     "against the four U.FL sites ANT1..ANT4 actually drawn, and the two "
     "2.4 GHz-capable feeds stay SEPARATE as ADR-029 D3 requires (ANT2 "
     "ranging, ANT3 link RX; never co-polarised within lambda/2). Antennas "
     "are hub-side wire dipoles per ADR-009, so a wing cut costs no comms. "
     "The SX1280 RFIO pad number (14) is still ADR-045 D1 OPEN-13-"
     "TODO(unverified) - the net is named, the pad number is not proven."),
    ("ANT3_2G4_RX", [("U3", "10"), ("ANT3", "1")],
     "ADR-034 D1: bare LoRa2021 2.4 GHz feed."),
    ("ANT4_GNSS_L1", [("U5", "11"), ("ANT4", "1")],
     "ADR-029 D3: MAX-M10S RF_IN -> GNSS L1 U.FL."),
    # --- ADR-108 Revision R1: the bare-module control lines (OPEN-3/OPEN-14) ---
    # The +4 GPIO budget of docs/V9-RADIO-SITE-MATRIX.md 3.1 (CS + BUSY +
    # RESET + IRQ/DIO, shared SPI data/clock) is spent on the only four
    # ESP32-S3 GPIOs that are free after the straps (IO0/IO3/IO45/IO46, ADR-108
    # strapping audit), the octal-PSRAM pins (IO35/36/37, -N8R8) and the USB
    # console (IO19/IO20): IO11, IO12, IO47, IO48. IO11 is free because the
    # F33 has NO DIO5 pad (OPEN-6), and its ENABLE routing is the one the
    # reference supplies; IO12/IO47/IO48 are the three pins OPEN-14 recorded
    # as unassigned. Spending all four here is the documented consequence:
    # no free GPIO remains, so OPEN-25 cut-sense must multiplex (ADR-051 2.6).
    ("U3_CS_N", [("U1", "20"), ("U3", "6")],
     "ADR-108 Revision R1 CLOSES OPEN-3: bare LoRa2021 NSS (pad 6) on "
     "IO12 (U1 pin 20), the first of the +4 GPIO budget in "
     "docs/V9-RADIO-SITE-MATRIX.md 3.1 and ADR-040 D2. U3 shares the SPI2 SCK/MOSI/MISO "
     "data and clock with the F33 (F33_SCK/F33_MOSI/F33_MISO) and needs its own chip select "
     "because SPI2 has two slaves. CLOSES the U1.20 half of OPEN-14."),
    ("U3_BUSY", [("U1", "24"), ("U3", "7")],
     "ADR-108 Revision R1 CLOSES OPEN-3: bare LoRa2021 BUSY (pad 7) on "
     "IO47 (U1 pin 24) - the arbiter reads BUSY by GPIO without driver "
     "cooperation (ADR-029 D4 R3). CLOSES the U1.24 half of OPEN-14."),
    ("U3_RESET_N", [("U1", "25"), ("U3", "14")],
     "ADR-108 Revision R1 CLOSES OPEN-3: bare LoRa2021 RESET (pad 14) on "
     "IO48 (U1 pin 25). CLOSES the U1.25 half of OPEN-14."),
    ("U3_IRQ", [("U1", "19"), ("U3", "15")],
     "ADR-108 Revision R1 CLOSES OPEN-3: bare LoRa2021 IRQ/DIO9 (pad 15, "
     "the vendor pin table name in docs/assets/lr2021/"
     "LoRa2021-Module-Datasheet-V1.3.pdf s7) on IO11 (U1 pin 19). IO11 was "
     "assigned to F33_DIO5 in the original pin plan; OPEN-6 established the "
     "F33 has NO DIO5 pad (all 18 pads enumerated, the front-end DIOs are "
     "internal) and freed IO11 for exactly this kind of re-assignment. That "
     "makes four control lines for the second radio - the +4 of "
     "docs/V9-RADIO-SITE-MATRIX.md 3.1 - and it removes the F33_DIO5 "
     "no-connect from V9_NC."),
    # --- ADR-058: the LR2021 on-chip NTC temperature-compensation provision. ---
    ("VTCXO_VNTC", [("U3", "13"), ("R_NTC1", "1")],
     "ADR-058 D1: the VTCXO/VNTC bias rail of the on-chip temperature-"
     "compensation divider, taken from the bare module's pad 13 = VTCXO (vendor "
     "pin table docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf s7: "
     "'Can provide power for an external TCXO'). DS 2.2 Table 2-1 names the chip "
     "pin it carries, pin 6 = VTCXO/VNTC, 'External TCXO supply voltage "
     "(REG_TCXO) / NTC supply'; DS 2.2 s1.9.2 says this pin 'can be used to power "
     "an external temperature sensor (R and NTC)'. R_NTC1 pin 1 sits on it - the "
     "divider is the only load here, a microwatt fraction of the regulator's "
     "ILTCXO 1.5 mA typ / 4 mA max (DS 2.2 Table 3-25). NO PWR_FLAG is implied: "
     "the net carries passive pins only."),
    ("NTC_SENSE", [("R_NTC1", "2"), ("TH_NTC1", "1")],
     "ADR-058 D1/D6: the divider's midpoint - THE NORMAL SENSE NODE that the "
     "chip's NTC input (chip pin 3, DS 2.2 Table 2-1 'Negative Temperature "
     "Coefficient (NTC) resistor connection') is meant to read. It is a "
     "DELIBERATELY OPEN LOOP on the owned bare module: the chip's NTC pin is NOT "
     "broken out on the NiceRF module's 18 castellations (the vendor pin table "
     "enumerates all 18 pads and the only oscillator pad is 13 = VTCXO; module "
     "pad 3 is MISO), so this node has no path back to the chip. The parts are "
     "DNP for exactly that reason and the node is left as the two-part divider "
     "node rather than given an invented chip-side net. A module that DOES break "
     "the pin out closes the loop here - see OPEN-29."),
]

# --- ADR-051 §2.1: the hub array's OWN nets, and the cut-sense lines. --------
# These nets carry the hub string and NOTHING ELSE: no W<n>_SOLAR_P and no
# W<n>_SOLAR_N land appears on any HUB_PV_* net, and the only node the hub
# string shares with the wing system is GND (through U_HUB_CVT pin 2).  That is
# the whole invariant ADR-051 §2.1 exists to protect - a hub array in series
# with, or tapped onto, the wing chain dies on the first cut, which turns the
# cut into suicide.  scripts/hub_array_topology_check.py is the mechanical
# enforcement (R3/R3b/R4/R5/R7).
V9_NETS.append(
    ("HUB_PV_P",
     [("PVA1", "1"), ("D_HUB1", "1"), ("U_HUB_CVT", "1")],
     "ADR-051 §2.1.1: the hub string's POSITIVE terminal and its own converter "
     "input node. Feeds U_HUB_CVT pin 1 - the hub array's OWN harvester/converter "
     "input, never the wing chain's BAT54/supercap node. D_HUB1 pin 1 is the "
     "first hub cell's bypass cathode."))
for _k in range(1, V9_HUB_ARRAY_CELLS):
    V9_NETS.append(
        ("HUB_PV_MID%d" % _k,
         [("PVA%d" % _k, "2"), ("PVA%d" % (_k + 1), "1"),
          ("D_HUB%d" % _k, "2"), ("D_HUB%d" % (_k + 1), "1")],
         "ADR-051 §2.1.1: interior node %d of the hub series string (between "
         "hub cells %d and %d). It is INTERNAL to the hub array: it carries no "
         "wing land, and sharing it with the wing chain is exactly the tap the "
         "topology checker fails on (R4)." % (_k, _k, _k + 1)))
V9_NETS.append(
    ("HUB_PV_N",
     [("PVA%d" % V9_HUB_ARRAY_CELLS, "2"),
      ("D_HUB%d" % V9_HUB_ARRAY_CELLS, "2"), ("U_HUB_CVT", "3")],
     "ADR-051 §2.1.1: the hub string's NEGATIVE terminal, wired to the hub "
     "converter\'s own PV_N input (U_HUB_CVT pin 3) and to the last hub cell's "
     "bypass anode. It carries NO wing land: the only node the hub string "
     "shares with the wing system is GND, and that is through the converter\'s "
     "ground pin, not through a W<n>_SOLAR_N land. (ADR-051 §2.1.2.)"))

for _i in range(1, 5):
    V9_NETS.append(
        ("CUT_SENSE_W%d" % _i,
         [("J_W%d" % _i, "3"), ("U_CUT%d" % _i, "3")],
         "ADR-051 §2.6: the per-wing cut-sense / cutter line on the wing "
         "tab's RESERVED pin 3 (RF_FEED). Netting it CLOSES the four "
         "pin_not_connected ERC errors the unnetted provision produced, at "
         "zero connector cost - the land and the position were already paid "
         "for. Honest caveat: on the v9 WING, RF_FEED is a copper land with no "
         "net, so the continuity measurement only becomes meaningful once the "
         "wing is re-spun to tie RF_FEED into the cut loop\'s return (OPEN-25, "
         "ADR-051 §2.6 caveat + §4 item 9)."))

# --- ADR-051: the new hub-array / cut-channel components' power and ground pins.
# Their OWN nets are appended above; the two SHARED rails are extended here so
# every added pin lands on the same node the rest of the sheet already uses.
# This is deliberate: a new component with an unnetted pin would ADD a
# pin_not_connected ERC error, and the point of netting the RF_FEED lands is to
# CLOSE errors, not trade them.
_GND_EXTRA = [("U_HUB_CVT", "2")] + [("U_CUT%d" % _i, "2") for _i in range(1, 5)]
_VSCAP_EXTRA = [("U_CUT%d" % _i, "1") for _i in range(1, 5)]
for _idx, (_n, _nodes, _src) in enumerate(V9_NETS):
    if _n == "GND":
        V9_NETS[_idx] = (_n, list(_nodes) + _GND_EXTRA,
                         _src + " ADR-051: this net also carries the hub "
                         "converter's ground pin (U_HUB_CVT.2) and the four "
                         "latched cut channels' ground pins (U_CUT1..4.2) - it is "
                         "the ONE node the hub string shares with the wing system.")
    elif _n == "VSCAP":
        V9_NETS[_idx] = (_n, list(_nodes) + _VSCAP_EXTRA,
                         _src + " ADR-051 s2.5: this net is also the cut "
                         "channels' drive rail (U_CUT1..4.1) - VSCAP is the raw "
                         "supercap node, post-BAT54 and PRE-LDO, so a cut still "
                         "works with the converter dead (ADR-047 s2.1).")

# --- deliberately unconnected pins, each with the record that says so ------
V9_NC = [
    ("U1", "27", "IO0 boot strap: no radio pull-up/CS (ADR-029 pin plan, "
                 "strapping audit)."),
    ("U1", "15", "IO3 boot strap: no sensor/radio connection (pin plan)."),
    ("U1", "26", "IO45 boot strap: vendor strap level, no external load (pin plan)."),
    ("U1", "16", "IO46 boot strap: vendor strap level, no external load (pin plan)."),
    ("U1", "28", "IO35 = octal-PSRAM connection on -N8R8, not a board GPIO "
                 "(ADR-029 D1.1 / pin plan)."),
    ("U1", "29", "IO36 = octal-PSRAM connection (ADR-029 D1.1 / pin plan)."),
    ("U1", "30", "IO37 = octal-PSRAM connection (ADR-029 D1.1 / pin plan)."),
    ("U5", "5", "MAX-M10S EXTINT unused (carried from the v8i board audit)."),
    ("U5", "13", "MAX-M10S LNA_EN unused (v8i board audit)."),
    ("U5", "14", "MAX-M10S VCC_RF unused (v8i board audit)."),
    ("U5", "16", "MAX-M10S SDA unused - v9 GNSS is UART, not I2C (v8i audit)."),
    ("U5", "17", "MAX-M10S SCL unused - v9 GNSS is UART, not I2C (v8i audit)."),
    ("U2", "10", "F33 ANT-2G4 port RETIRED. ADR-034 D5: 'the F33 carries "
                 "TX only' - its pin-9 sub-GHz port is the 433 MHz TX, and "
                 "the 2.4 GHz link RX was re-pointed at the bare LoRa2021 "
                 "(ADR-034 D1). With only four U.FL sites, ANT2 goes to the "
                 "SX1280 ranging radio (ADR-108 Revision R1, OPEN-2) and this "
                 "port has no destination. Not equipped, not a stub: no "
                 "matching network is fitted either (ADR-029 D8 item 2 - DNP "
                 "pads, never open stubs)."),
    ("U3", "9", "Bare LoRa2021 sub-GHz ANT (pad 9) is unused in EVERY "
                 "documented population configuration. ADR-034 D1 puts the "
                 "433 MHz TX on the Site-A module (whose pad 9 shares the "
                 "F33 land - ADR-040 D1 nested pad field - and therefore "
                 "reaches ANT1), and Site B is the LP-only 2.4 GHz RX site "
                 "(ADR-040 D1/D2, docs/V9-RADIO-SITE-MATRIX.md 3.3/3.4). "
                 "In {HP} Site B is DNP. So this port is not 'unconditionally "
                 "unused by reflex' - it is unused because in all four "
                 "configurations the TX role sits on the Site-A module. "
                 "CLOSES OPEN-4; a future re-point would need a fifth feed."),
    ("U3", "16", "Bare LoRa2021 DIO8 (vendor pin table, "
                 "docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf s7). "
                 "The LR2021 DIO5-8 are the RF FRONT-END control lines "
                 "(docs/LR2021-LESSONS-2026-09.md), and this module has NO "
                 "front end: the bare NiceRF LoRa2021 is chip-only (needs an "
                 "external FEM for a 2.4 GHz PA, docs/F33-MODULE-PLAN.md) and "
                 "ADR-034 D1 item 2 deliberately leaves the airborne 2.4 GHz "
                 "RX unamplified. Nothing to control, and no GPIO left. "
                 "CLOSES OPEN-5."),
    ("U3", "17", "Bare LoRa2021 DIO7 (vendor pin table s7) - same reasoning "
                 "as pad 16: a front-end control line on a module with no "
                 "front end. CLOSES OPEN-5."),
    ("U5", "15", "MAX-M10S VIO_SEL is LEFT OPEN by its own datasheet. u-blox "
                 "MAX-M10S datasheet UBX-20035208-R08 Table 10, pin 15: "
                 "'Voltage selector for V_IO supply. Connect to GND for 1.8 V "
                 "supply, or leave open for 3.3 V supply.' The v9 GNSS IO "
                 "supply U5 pin 7 (V_IO) is +3V3, so 3.3 V is the correct "
                 "range and the pin must stay open. Tying it to GND would "
                 "select the 1.8 V range and put 3.3 V on a pin whose "
                 "absolute maximum in that state is 1.98 V (Table 12). The "
                 "frozen v8i board's netless pad 15 is therefore CORRECT, not "
                 "a recorded gap. CLOSES OPEN-8."),
    ("U5", "18", "MAX-M10S SAFEBOOT_N is LEFT OPEN by its own datasheet. "
                 "UBX-20035208-R08 Table 10, pin 18: 'Safeboot mode (active "
                 "low). Leave open if not used.' (footnote 15: the pin is "
                 "internally tied to TIMEPULSE through a 1 kOhm series "
                 "resistor and has its own pull-up, Table 12 Rpu). Safeboot "
                 "is a recovery mode; the v9 receiver runs in continuous "
                 "mode. CLOSES OPEN-8."),
    ("U7", "4", "TPS7A02 pin 4 is NC ON THE PART. TI datasheet SBVS277C "
                 "(Rev C) Table 5-1 / Figure 5-2, DBV (SOT-23, 5): pin 1 IN, "
                 "pin 2 GND, pin 3 EN, pin 4 NC ('No connect pin. This pin is "
                 "not internally connected. Connect to ground or leave "
                 "floating.'), pin 5 OUT. The sheet symbol's own 'NC' label "
                 "is RIGHT; the frozen boards are wrong to tie pad 4 to +3V3 "
                 "(v8i/v8j/v8b/v8c/v8f) - harmless because the pad is not "
                 "internally connected, but it is not what the datasheet asks "
                 "for, so it is NOT adopted; hub_board_v1_clean (pad 5 = OUT) "
                 "has the correct pin map and confirms this reading. CLOSES "
                 "OPEN-9."),
]

# --- explicit TODO(unverified) open questions, never guessed ---------------
# NOTE (ADR-047): OPEN-1 "5 V RAIL" is CLOSED. The operator's 2026-10-07
# directive ("provision more than enough power for the maximum draw that F33 can
# draw ... a hard design requirement") is implemented by ADR-047 on top of
# ADR-044 option (a): U2 pin 1 is now on F33_VCC, fed PRE-LDO from the supercap
# node through the ADR-029 D8 pin-1 selector, with a local bulk cap, a clamp and
# a rail monitor. The remaining entries below are still OPEN.
V9_TODO = [
    ("OPEN-1 SX1280 SUPPLY (U4 pins 1,2) - CLOSED 2026-10-07 R1",
     "SX1280 VDD_IN/VDD_IO rail not fixed by any record and the Semtech "
     "datasheet is unreachable here. Left open deliberately. ADR-060 s5 "
     "(2026-10-07) RE-FILES this as unfixed, which is why it stays open. The "
     "conflict to resolve: ADR-047 states the 3.3 V rail also carries the "
     "SX1280, and docs/POWER-BUDGET-V9-D2BE.md s2 lists both SX1280 states on "
     "the 3.3 V rail - so a one-line amendment moving U4 pins 1,2 onto +3V3 is "
     "what closes it. >>> CLOSED 2026-10-07 by ADR-108 Revision R1: U4 pins "
     "1 and 2 are on +3V3. ADR-047 2.3 (the 3.3 V rail also carries the "
     "SX1280) + POWER-BUDGET-V9-D2BE.md 2 (both SX1280 states on 3.3 V). No "
     "new or gated rail (ADR-060 s4). The ADR-029 2(f) ferrite + bulk cap is "
     "still owed - see OPEN-33.<<<"),
    ("OPEN-2 SX1280 RF PORT (U4 pin 14 RFIO) - CLOSED 2026-10-07 R1",
     "No antenna feed is assigned to the SX1280 RFIO. ADR-029 D3 enumerates the "
     "FOUR connectors as {GNSS, F33 sub-GHz, F33 ANT-2G4, SX1280}, but ADR-034 "
     "D1 re-points the 2.4 GHz RX at a SEPARATE bare LoRa2021 that also needs a "
     "feed. Exactly one of the two is left without a listed feed - resolve "
     "before fabricating. No tie-off guessed. ADR-045 D1 records the SX1280's "
     "antenna pin number itself as TODO(unverified) (no datasheet committed), "
     "so not even the pad is certain. ADR-060 s5 re-files this too (U4 pin 14). "
     "OWNER: the ADR-108 pin-plan revision, which must also settle the "
     "four-connector / five-feed count (ADR-029 D3 vs ADR-034 D1). >>> "
     "CLOSED 2026-10-07 by ADR-108 Revision R1: the count is FOUR feeds for "
     "the four RF parts of ADR-034 D5, one per U.FL site. ANT2 is re-pointed "
     "from the F33 2.4 GHz port (retired - ADR-034 D5 'the F33 carries TX "
     "only') to the SX1280 RFIO; ANT1 433 TX, ANT3 bare 2.4 RX, ANT4 GNSS. "
     "The SX1280 pad number stays ADR-045 D1 TODO(unverified). <<<"),
    ("OPEN-3 BARE-MODULE CONTROL LINES (U3 pins 6,7,14,15) - CLOSED 2026-10-07 R1",
     "ADR-034 adds the bare LoRa2021 but NO record assigns its NSS/BUSY/RESET/"
     "IRQ GPIOs (the ADR-029 pin plan predates ADR-034). Left floating - "
     "the +4 GPIO budget in V9-RADIO-SITE-MATRIX 3.1 must be spent first. No "
     "record assigns NSS/BUSY/RESET/IRQ for the bare module (ADR-108 covers "
     "F33 + SX1280 only). OWNER: the ADR-108 pin-plan revision together with "
     "the ADR-040 / V9-RADIO-SITE-MATRIX 3.1 GPIO-budget decision. >>> "
     "CLOSED 2026-10-07 by ADR-108 Revision R1: the +4 budget of "
     "docs/V9-RADIO-SITE-MATRIX.md 3.1 is spent on the only four free "
     "ESP32-S3 GPIOs - U3.6 NSS -> IO12, U3.7 BUSY -> IO47, U3.14 RESET -> "
     "IO48, U3.15 IRQ/DIO9 -> IO11 (freed by OPEN-6). U3 shares the SPI2 "
     "data/clock. This also disposes of U1 pins 20/24/25 (OPEN-14). <<<"),
    ("OPEN-4 BARE-MODULE SUB-GHz PORT (U3 pin 9 ANT) - CLOSED 2026-10-07 R1",
     "Unused under ADR-034 (U3 is the 2.4 GHz RX). An RF port is not tied off "
     "without a decision - left open. OWNER: the ADR-034 / ADR-040 population "
     "decision - in the {LP} configuration a bare module can be the 433 MHz "
     "TX (V9-RADIO-SITE-MATRIX 3.3), so this port is not unconditionally "
     "unused and no no-connect is asserted. >>> CLOSED 2026-10-07 by "
     "ADR-108 Revision R1: the population "
     "case IS decided - ADR-034 D1 puts the 433 MHz TX on the Site-A module "
     "(shared pad 9 -> ANT1) and Site B is the LP-only 2.4 GHz RX site "
     "(ADR-040 D1/D2, matrix 3.3/3.4); in {HP} Site B is DNP. So the Site-B "
     "sub-GHz port has no role in ANY of the four configurations and is a "
     "justified no-connect, not a reflex. <<<"),
    ("OPEN-5 BARE-MODULE PAD FUNCTIONS (U3 pins 13,16,17) - CLOSED 2026-10-07 R1",
     "PAD13/PAD16/PAD17 functions were unverified (v8i audit: DECLARED_GAP). "
     "PARTLY CLOSED by ADR-058 s1.3: pad 13 = VTCXO - the vendor pin table "
     "docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf s7 enumerates all 18 "
     "pads and names pad 13 'VTCXO', O, 'Can provide power for an external TCXO', "
     "so the generator's placeholder 'PAD13_??' is renamed 'VTCXO' (a naming "
     "correction with a source; no connectivity added). STILL OPEN: pads 16 and 17 "
     "(PAD16_??/PAD17_??) - the vendor table calls them DIO8 and DIO7 but the "
     "generator's bare-module pin map has not been reconciled with it. See also "
     "OPEN-29 (the chip's NTC pin has no castellation). Pads 16/17 are now NAMED "
     "DIO8/DIO7 (vendor pin table s7 + docs/inventory.md line 28 - a naming "
     "correction, no connectivity); what REMAINS OPEN is the MCU ASSIGNMENT, "
     "which no record fixes. >>> CLOSED 2026-10-07 by ADR-108 Revision R1: "
     "pads 16 and 17 are a justified no-connect. The LR2021 DIO5-8 are the "
     "RF front-end control lines (docs/LR2021-LESSONS-2026-09.md) and this "
     "module has NO front end - the bare NiceRF LoRa2021 is chip-only "
     "(docs/F33-MODULE-PLAN.md) and ADR-034 D1 item 2 deliberately leaves the "
     "airborne 2.4 GHz RX unamplified. There is nothing for DIO7/DIO8 to "
     "drive, and no GPIO remains. <<<"),
    ("OPEN-6 F33 DIO5 (U1 pin 19) - CLOSED 2026-10-07",
     "ADDRESSED: F33_DIO5 has NO destination on the fitted F33 module, so U1 "
     "pin 19 (IO11) is a no-connect. The F33's own 18-pad table (G-NiceRF "
     "LoRa2021F33-2G4 datasheet Rev 1.1 s7, quoted in-repo at ADR-059 s1.3) "
     "enumerates EVERY pad - 1 VCC / 2,3,4,6,7,8,11 GND / 5 CE / 9 ANT / 10 "
     "ANT-2G4 / 12 SCK / 13 NSS / 14 BUSY / 15 MOSI / 16 MISO / 17 RESET / 18 "
     "IRQ - and lists NO DIO5 pad, and the v9 F33 symbol defines no DIO5 pin. "
     "docs/F33-MODULE-PLAN.md (No DIO7/DIO8/DIO9 pins - only IRQ (Pin 18) as "
     "digital interface) and docs/LR2021-LESSONS-2026-09.md (DIO5-8 are "
     "LR2021 DIOs wired to the on-module front-end; setRfSwitchTable writes "
     "the mode mask into the CHIP, not MCU GPIOs) both confirm the F33 "
     "front-end DIOs are internal. No net was invented and nothing was "
     "silenced: IO11 is NC. OWNER: a future ADR-108 pin-plan revision must "
     "re-assign IO11 if a DIO5-class interrupt is ever needed. >>> "
     "RE-ASSIGNED 2026-10-07 by ADR-108 Revision R1: the free IO11 (U1 pin "
     "19) is spent as the bare module's IRQ line (U3_IRQ, OPEN-3). U1 pin 19 "
     "is therefore no longer a no-connect. <<<"),
    ("OPEN-7 MS5611 TIE-OFFS (U6 pins 2,4,6) - CLOSED 2026-10-07",
     "ADDRESSED by the frozen v8j MS5611 board: "
     "tracker/hardware/output/v8j_krt_ms5611.kicad_pcb carries the barometer "
     "on the SAME footprint this sheet uses - Package_LGA:LGA-8_3x5mm_P1.25mm "
     "- in the SAME I2C mode (its pads 7/8 are I2C_SDA / I2C_SCL, exactly "
     "this sheet U6 pins 7/8), and it ties pad 2 = GND, pad 4 = +3V3 and pad "
     "6 = GND. A frozen board carrying the same footprint is citable "
     "authority for a pin tie-off, so this sheet follows it: U6.2 (PS) -> "
     "GND, U6.4 (CSB) -> +3V3, U6.6 (SDO) -> GND. The v8i board is NOT the "
     "precedent (its barometer is a Bosch LGA-8 2.5x2.5 mm pad field, a "
     "different part footprint); v8j is. TODO(unverified): no MS5611 "
     "datasheet is committed, so the tie-off LEVELS come from the board "
     "precedent rather than a vendor table. OWNER: none - closed from the "
     "landed v8j artefact."),
    ("OPEN-8 MAX-M10S TIE-OFFS (U5 pins 15,18)",
     "VIO_SEL (15) and ~SAFEBOOT (18) were netless DECLARED_GAP pins on the "
     "frozen v8i board and no record fixes them. V_BCKP / VCC_IO / ~RESET "
     "(pins 6/7/9) are NO LONGER open: the v8i board - same ublox_MAX footprint "
     "and same RF_GPS:MAX-M10S symbol - ties 6/7/8/9 to +3V3, and this sheet "
     "follows that precedent. VERIFIED against the frozen board: "
     "tracker/hardware/output/v8i_krt_gnss.kicad_pcb (same ublox_MAX "
     "footprint + RF_GPS:MAX-M10S symbol) leaves pads 15 and 18 UNNETTED - "
     "the precedent records the gap rather than deciding it, so no tie-off is "
     "adopted and no no-connect is asserted. OWNER: the ADR-108 pin-plan "
     "revision (no MAX-M10S datasheet is committed here). >>> CLOSED "
     "2026-10-07 by ADR-108 Revision R1: the datasheet was obtained. u-blox "
     "MAX-M10S UBX-20035208-R08 Table 10: pin 15 VIO_SEL 'Connect to GND for "
     "1.8 V supply, or leave open for 3.3 V supply' and pin 18 SAFEBOOT_N "
     "'Leave open if not used'. V_IO (U5 pin 7) is +3V3, so BOTH are left "
     "open - which is what the v8i precedent recorded, now confirmed as a "
     "decision rather than a gap. Tying VIO_SEL low would exceed its 1.98 V "
     "absolute maximum at V_IO = 3.3 V (Table 12). <<<"),
    ("OPEN-9 TPS7A02 NC (U7 pin 4) - CLOSED 2026-10-07 R1",
     "TPS7A02 pin 4 is a real pad with an unverified function: the v8i board "
     "leaves it netless (DECLARED_GAP 'TPS7A02 pin 4 function / tie-off'), and "
     "no datasheet for the part is committed here. Deliberately NOT given an "
     "invented tie-off or a no_connect flag, because the flag would assert a "
     "decision no record makes. NOTE the sheet's own repo-local symbol "
     "(v9_lib/balloon_flight_v9.kicad_sym) names U7 pin 4 'NC', which "
     "CONTRADICTS this entry, and the frozen boards are inconsistent too "
     "(v8i/v8j/v8b/v8c/v8f tie the SOT-23-5 pad 4 to +3V3; output/v8_krt_routed "
     "and hub_board_v1 leave it netless). No tie-off is adopted from a "
     "contradiction. OWNER: the ADR-108 pin-plan revision, once a TPS7A02 "
     "datasheet is obtained. >>> CLOSED "
     "2026-10-07 by ADR-108 Revision R1: the datasheet was obtained. TI "
     "TPS7A02 SBVS277C Table 5-1 / Figure 5-2 (DBV, SOT-23-5): pin 4 IS NC "
     "('not internally connected. Connect to ground or leave floating'). "
     "The no-connect is therefore what the part asks for, and the frozen "
     "boards that tie pad 4 to +3V3 are NOT adopted; hub_board_v1_clean (its "
     "pad 5 = OUT) confirms the correct pin map. <<<"),
    ("OPEN-10 ESP32-S3 EN and USB (U1 pins 3,13,14) - STILL OPEN, now SPECIFIED",
     "Module EN strap and the USB_D-/USB_D+ pads have no v9 connector or "
     "recorded tie-off. The ADR-029 pin plan calls USB-Serial-JTAG the assumed "
     "debug path, so these are not unused - they lack a termination. The reset "
     "RC is also absent from the v9 BOM "
     "(docs/coordination/SCHEMATIC-PLAN-3VARIANTS.md 5 item 2). ADR-108 assigns "
     "the FUNCTION of GPIO19/20 (USB_D-/D+ = USB-Serial-JTAG console, no "
     "external radio use) but names no connector and no EN reset RC, and the "
     "v9 BOM has neither. OWNER: the ADR-108 pin-plan revision - a connector "
     "part and the reset-RC values must be named before either can be netted. "
     ">>> PARTLY SETTLED 2026-10-07 by ADR-108 Revision R1 - the DECISION is "
     "now recorded, the three pins stay OPEN because the connector is not "
     "fitted and this revision adds no part. RECOMMENDED CONSOLE / RESET "
     "CONNECTOR: the same 6-pin 2.54 mm programming header the frozen v8i "
     "board already uses as J1 'Prog_Header' - footprint/part id "
     "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical (already in "
     "the generator's PART_MAP as Connector_Generic:Conn_01x06), wired 1 GND "
     "/ 2 +3V3 / 3 EN / 4 USB_D- / 5 USB_D+ / 6 IO0 (the v8i precedent carries "
     "GND/3V3/EN/UART0-RX/UART0-TX/IO0 - the ESP32-S3 console is "
     "USB-Serial-JTAG, so UART0 TX/RX are replaced by USB_D-/D+, exactly as "
     "ADR-108's table assigns GPIO19/20). RESET RC: R = 10 kOhm and C = 1 uF, "
     "ESP32-S3-WROOM-1 & WROOM-1U datasheet v1.8 s9 (Peripheral Schematics, "
     "p.41): 'it is advised to add an RC delay circuit at the EN pin. The "
     "recommended setting for the RC delay circuit is usually R = 10 kOhm and "
     "C = 1 uF.' U1.3 EN -> the RC + header pad 3; U1.13/U1.14 -> header pads "
     "4/5. OWNER: the pass that adds the console connector to the BOM - the "
     "part, the pinout and the RC values are no longer undecided, only unfitted. <<<"),
    ("OPEN-11 SUPERCAP ADC GPIO",
     "ADR-006 puts the supercap ADC on GPIO0; the ADR-029 pin plan reserves "
     "IO0 as a boot strap and forbids loading it. The divider tap net exists "
     "but its MCU end is unresolved. (Note: this sheet's NEW rail monitor does "
     "not use GPIO0 - see OPEN-17.)"),
    ("OPEN-12 SOLAR INPUT SOURCE (CLOSED by ADR-048)",
     "ADDRESSED: the 4-wing x 3-cell solar array input IS the four wing-mounted "
     "interfaces J_W1..J_W4 added by ADR-048 (ADR-046 s1/s2.3 + socket spec s1). "
     "The net that used to be a 1-pad `SOLAR_IN` (D1 anode only) is now "
     "W1_SOLAR_P and carries J_W1 pad 1 as the stack top. What is NOT closed: "
     "the wing-side array-coverage / bypass re-budget of ADR-046 s2.3 (the 6.0 V "
     "/ 2.4 W ADR-006 budget is only valid with all four wings illuminated)."),
    ("OPEN-13 SX1280 PIN NUMBERS + LAND PATTERN",
     "The Semtech SX1280 datasheet could not be retrieved on this host. The "
     "symbol's QFN pad numbering and SX1280_QFN24.kicad_mod geometry are "
     "PLACEHOLDERS - every SX1280 pin is TODO(unverified). ADR-045 D1 files the "
     "same gap as a blocker for its antenna-access gate."),
    ("OPEN-14 UNASSIGNED ESP32-S3 GPIO (U1 pins 20,24,25 = IO12, IO47, IO48) - CLOSED 2026-10-07 R1",
     "The ADR-029 pin plan does not assign these, and the strapping audit only "
     "clears IO0/IO3/IO45/IO46 as straps and IO35-IO37 as PSRAM. Left floating "
     "rather than guessed: assign them deliberately in a pin-plan revision, or "
     "mark them no_connect on the record. ADR-108 (the pin plan) assigns IO0, "
     "IO3, IO45 and IO46 'none' - they are NC on this sheet - and reserves "
     "IO35-37 for octal PSRAM, but it states NO disposition for IO12, IO47 and "
     "IO48, and this register's own instruction is that a RECORD must decide "
     "them. Undecided -> not silenced. OWNER: the ADR-108 pin-plan "
     "revision. >>> CLOSED 2026-10-07 by ADR-108 Revision R1: U1 pins 20, "
     "24 and 25 (IO12 / IO47 / IO48) are ASSIGNED, not no-connects - they are "
     "the bare module's NSS / BUSY / RESET lines (U3_CS_N / U3_BUSY / "
     "U3_RESET_N) per the +4 GPIO budget of docs/V9-RADIO-SITE-MATRIX.md 3.1 "
     "and ADR-040 D2. No free GPIO remains on the module afterwards. <<<"),
    ("OPEN-15 SUPERCAP CELL ESR + COLD BANK BEHAVIOUR",
     "ADR-047 3/4: the AVX SCC 3.3 F 2.7 V cell's ESR is NOT in this "
     "repository, at 25 C or at -60 C. Every rail-step number in ADR-047 is "
     "conditional on the assumed 0.10 Ohm/cell. ADR-029 5 test 4 (<20 mV rail "
     "dip during a worst-case burst) is NOT met by scaling this cell family: "
     "16.7 mOhm would need ~12 cells in parallel per series position."),
    ("OPEN-16 CLAMP SET POINT (D_CLAMP)",
     "ADR-047 7: the clamp must conduct above the 5.4 V rail top and below the "
     "F33's damage threshold, which Rev 1.1 of the datasheet does not publish; "
     "the 12-cell array's open-circuit voltage at -60 C is also unmeasured. "
     "Part and set point cannot be finalised - do not order a guess."),
    ("OPEN-17 RAIL-MONITOR ADC CHANNEL (U1 pin 21 = IO13)",
     "ADR-047 6: IO13 is unassigned by the ADR-029 pin plan, and ADR-038 D1 "
     "makes Wi-Fi/BT never enabled (CONFIG_ESP_WIFI_ENABLED=n), which is the "
     "condition normally attached to ESP32-S3 ADC2 use. Those two facts are the "
     "whole basis for putting the monitor there. The ADC channel number and the "
     "ADC's required source impedance are NOT in this repository, and the pin "
     "plan has not yet been amended to record the assignment."),
    ("OPEN-18 O5 EVIDENCE STILL OPEN",
     "ADR-029 O5 / ADR-044 7: no 5 V chain demonstrated at >=1.2 A load-step "
     "capability, no 3.3 V rail at >=0.60 A transient, no cold supercap or "
     "regulator evidence, no ADR-029 5 test 4. ADR-047 sizes for the maximum "
     "draw; it does not measure the chain. The BOM freeze stays gated on this."),
    ("OPEN-19 ANTENNA SOLDER ACCESS (ADR-045)",
     "ADR-045 does NOT change the antenna connector count or these net names: "
     "ADR-029 D3's four U.FL feeds stand, and ADR-045 gates PLACEMENT, not "
     "netlist. Its requirement is that every antenna-port pad of BOTH LoRa2021 "
     "modules, of the SX1280 and of the GNSS feed be reachable by a soldering "
     "iron from OUTSIDE the module body, enforced by "
     "tracker/hardware/tools/antenna_access_check.py (exit 0 required) before "
     "the placement freezes. ADR-045 D1 leaves the SX1280 antenna pad and the "
     "MAX-M10S RF_IN pad TODO(unverified), which is why OPEN-2 and OPEN-13 "
     "cannot be closed here."),
    ("OPEN-20 HUB-SIDE LAND DATUM + EDGE CLEARANCE (ADR-048 D-1)",
     "The socket spec s2 gives the land row's along-insertion offset twice and "
     "incompatibly: 'Land centre offset from the hub's outer edge 1.0 mm inboard' "
     "versus its own parenthetical 'lands span 0.0...4.0 mm from the edge' "
     "(centre 2.0 mm) - a 1.0 mm self-contradiction - while ADR-046 s2.2 fixes "
     "copper-to-board-edge clearance >= 1.0 mm and the socket spec s2/s4 says "
     ">= 0.5 mm. ADR-048 implements the ADR number (>= 1.0 mm) and therefore sets "
     "the land row's near edge 1.0 mm inboard and its centre 3.0 mm from the "
     "interface edge; the lands then span 1.0..5.0 mm, inside the 6.0 mm "
     "insertion depth. TODO(unverified): which datum the records intend (land "
     "inboard edge at 1.0 mm, as implemented, or land centre at 1.0 mm, as the "
     "spec's table line reads). No in-repo source resolves it."),
    ("OPEN-21 W<n>_RF PROVISION LANDS (CLOSED by ADR-051 s2.6)",
     "ADDRESSED: ADR-046 s2.4 / socket spec s3.2 left each interface's pad 3 "
     "(RF_FEED) with its copper land but NO net, and explicitly said 'Do not tie "
     "it to GND'; that produced 4 pin_not_connected ERC errors by design. "
     "ADR-051 s2.6 now NETS that land as CUT_SENSE_W<n>, so those 4 errors are "
     "CLOSED at zero connector cost. The 'do not tie it to GND' prohibition "
     "STANDS and is honoured - the land sits on a named sense net, not on GND. "
     "What is NOT closed: the GPIO/divider assignment (OPEN-25) and the wing "
     "re-spin without which the continuity sense reads a floating pad "
     "(ADR-051 s2.6 caveat + s4 item 9)."),
    ("OPEN-22 HUB v9 STACK-UP / SLOT KEEP-OUT / FAB TOLERANCE",
     "Socket spec s8 items 1-4 are all still open: the hub's actual component "
     "keep-out at the slot (which owns whether the 6.0 mm slot depth is legally "
     "routable and whether the slot keep-out may exceed the +1.0 mm of s4); "
     "JLCPCB's routed-slot width tolerance (0.9 mm +/-0.10 mm is an ASSUMPTION, "
     "ADR-046 s4.3); the v9 hub layer count (the lands are on the two outer "
     "layers only); and whether the hub placement gate's component-to-interface "
     "clearance exceeds the 1.5 mm of socket spec s4. No v9 hub PCB exists, so "
     "none of these can be measured yet."),
    ("OPEN-23 WING ATTACH ORIENTATION — RESOLVED 2026-10-08 (ADR-049 s5 item 6)",
     "RESOLVED: the wing plane is VERTICAL (a blade) — long axis radial in the "
     "hub plane and pointing outward, 25 mm width vertical. Governing record: "
     "ADR-049 s5 item 6, resolved by the tab/slot arithmetic (ADR-046 s4.1: a "
     "0.9 mm slot admits a 0.6 mm tab plus a 0.30 mm gap, and a 9.0 mm tab "
     "cannot fit a 6.0 mm in-plane slot), corroborated by ADR-046 s4.1 ('90 deg "
     "to the hub plane, wing plane normal to the hub plane'), ADR-051 s1.4 and "
     "ADR-055 s1. The stale 'wings 1-2 horizontal' / 'long axis perpendicular "
     "to the hub plane' reading in WING-TO-HUB-SOCKET-SPEC s1 is v1-era prose "
     "(docs/hardware-design.md s3D-Assembly, an ANTENNA-coverage statement for "
     "a wing that carried a Yagi - V2-only and absent on v9, ADR-046 s2.4) and "
     "now carries an appended CORRECTION. The ADR-048 footprint's own decision "
     "is UNCHANGED: it asserts no rotation (datum = interface edge x slot "
     "centre line). Registered as 'wing_plane_orientation' in "
     "docs/ssot/parameters.json; gate scripts/param_ssot_check.py. STILL OPEN: "
     "TODO(unverified) whether the ~30 deg droop of wings 3-4 is retained on v9 "
     "- it had an antenna-coverage rationale only and no v9 record fixes it."),
    ("OPEN-24 HAND-SOLDER JOINT DIMENSIONS NOT MEASURED",
     "The v9 hub does not exist and neither the wing tab's nor the cells' real "
     "contact geometry has been measured: ADR-046 s7 item 1 files the 52 x 19 mm "
     "cell tab geometry as TODO(unverified), ADR-046 s7 item 8 files the tab "
     "fillet's structural adequacy under the ~176 mm cantilever as unanalysed, "
     "and ADR-046 s4.3 flags that a slot which comes out equal to the 0.6 mm tab "
     "is worse than no slot. The 0.30 mm nominal solder gap (0.9 mm slot - 0.6 mm "
     "tab, ADR-046 s4.1) is therefore the only gap number and it is unproven. "
     "Do not order a hub on these numbers alone."),
    ("OPEN-25 CUT-SENSE GPIO / DIVIDER AND THE WING RE-SPIN",
     "ADR-051 s2.6 fixes the MECHANISM (per-wing CUT_SENSE_W<n> on the reserved "
     "RF_FEED land) but NOT the GPIO count: four dedicated GPIOs, or one GPIO "
     "plus a 4:1 analogue mux / resistor-ladder encoding, are both compatible "
     "and the sense divider values are not chosen. GPIO budget is the "
     "constraint (ADR-029 free-GPIO audit; OPEN-14 records IO12/IO47/IO48 "
     "unassigned). Separately, the sense is only meaningful after the WING is "
     "re-spun to tie its RF_FEED land into the cut loop\'s return (ADR-051 s2.6 "
     "caveat + s4 item 9). >>> CONSEQUENCE RECORDED 2026-10-07 (ADR-108 "
     "Revision R1): the +4 GPIO budget is now fully spent (IO11/IO12/IO47/IO48 "
     "-> U3_IRQ/U3_CS_N/U3_BUSY/U3_RESET_N) and every other ESP32-S3 GPIO is "
     "an assignment, a strap (IO0/IO3/IO45/IO46), an octal-PSRAM pin "
     "(IO35/36/37) or the USB console (IO19/IO20). NO free GPIO remains, so "
     "the four CUT_SENSE_W<n> lines CANNOT take four dedicated GPIOs - the "
     "one-GPIO-plus-mux / resistor-ladder encoding ADR-051 2.6 allows is the "
     "only remaining shape. That choice, the divider values and the wing "
     "re-spin stay OPEN here. <<<"),
    ("OPEN-26 HUB ARRAY: CELL COUNT, MOUNTING PLANE, HARVESTER, OUTLINE",
     "ADR-051 s2.1's independence invariant is IMPLEMENTED on this sheet, but "
     "the array's PARAMETERS are not: the cell count (H2 = 2 recommended / H3 = "
     "3 fallback), the mounting plane (vertical 0.3051 vs horizontal 0.1865 "
     "day-mean - load-bearing for the area), the converter/harvester part and "
     "its peak-input-power rating, and the hub OUTLINE.  The count on this sheet "
     "is a DOCUMENTED PLACEHOLDER (V9_HUB_ARRAY_CELLS in "
     "build_flight_sch.py) because the hub outline is a form-factor decision "
     "owned by another task (ADR-051 s2.3). See ADR-051 s2.2 for H2's own 6 % "
     "shortfall and s4 items 3/4/5/6."),
    ("OPEN-27 HUB-ARRAY BYPASS GRANULARITY (PER-CELL vs PER-GROUP)",
     "ADR-051 s2.2 places the hub cells on the hub and says they 'need their own "
     "diodes'; ADR-054 s4.5 explicitly leaves the hub array's per-cell-over-"
     "per-group trade OPEN.  This sheet carries the MINIMAL per-cell provision "
     "(D_HUB<n>, one SS24 across each hub cell) because "
     "scripts/bypass_diode_check.py requires every solar series group - "
     "including an on-board cell - to be covered, and a determinate answer is "
     "worth more than a silent gap.  If the trade lands on per-group, the "
     "hub diodes regroup and this note is superseded."),
    ("OPEN-28 CUT-DRIVER LATCH TOPOLOGY AND ITS PART",
     "ADR-051 s2.5.1 mandates a LATCHED one-shot with a persistent NVS fired "
     "flag per channel plus a hardware series arming gate, but names no part: "
     "the IRLML2502 in the repo's own precedent is the switch, not the latch.  "
     "U_CUT1..U_CUT4 are PROVISION symbols whose pin set (VSCAP / GND / the "
     "wing RF_FEED line) is fixed and whose internals are TODO(unverified), as "
     "are the sense divider (OPEN-25), the on-time cap and the inter-cut "
     "interval.  Also open: the trigger mode - ground-commanded vs automatic "
     "(ADR-051 s2.5.7)."),
    ("OPEN-29 NTC PROVISION: THE MODULE PIN BREAK-OUT (ADR-058 D6, THE BLOCKER)",
     "Whether the LR2021 chip's NTC sense input (chip pin 3, 'Negative "
     "Temperature Coefficient (NTC) resistor connection', DS 2.2 Table 2-1) is "
     "broken out on the OWNED bare NiceRF module. EVIDENCE IN HAND SAYS NO: the "
     "vendor pin table (docs/assets/lr2021/LoRa2021-Module-Datasheet-V1.3.pdf s7) "
     "enumerates ALL 18 pads - 1 VCC / 2,8,11,12,18 GND / 3 MISO / 4 MOSI / 5 SCK "
     "/ 6 NSS / 7 BUSY / 9 ANT / 10 2.4/S_ANTA / 13 VTCXO / 14 RST / 15 DIO9 / 16 "
     "DIO8 / 17 DIO7 - and the only oscillator pad is 13 = VTCXO, described only "
     "as 'Can provide power for an external TCXO'. So the module brings out the "
     "VTCXO/VNTC BIAS rail but NOT the NTC SENSE input, and the divider midpoint "
     "(net NTC_SENSE) has no path back to the chip: SetTempCompCfg would configure "
     "a sensor that cannot be read. THAT is why R_NTC1/TH_NTC1 are DNP. WHAT WOULD "
     "SETTLE IT: the module MECHANICAL DRAWING (the vendor's pin-out drawing, not "
     "just the pin-definition table) or a DESHIELD PHOTO of a bare module's "
     "castellations. Until then the finding is strong but NOT promoted to 'proven "
     "absent' - a pin table can be an abbreviation and a module revision can "
     "differ (TODO(unverified); ADR-042 Addendum A2 files the same request). "
     "FALLBACK if unavailable (ADR-058 D6): do not fit the NTC on a bare module; "
     "fly the F33 (internal 0.5 ppm TCXO) or a TCXO-bearing LR2021 module; else "
     "firmware f(T) pre-distortion + GPS 1PPS discipline (ADR-056 D3)."),
    ("OPEN-30 NTC PART SELECTION AND ITS COLD RATING (ADR-058 D4/OPEN-2)",
     "TH_NTC1's part is NOT chosen. Required in this order: (1) read R25 and beta "
     "from the chosen part's own datasheet - they set SetNtcParams ntc_beta ('NTC "
     "temperature in 2 Kelvin/lsb', DS 2.2 Table 6-70) and, with R_NTC1, "
     "ntc_r_ratio; (2) CHECK THE COLD RATING against the -60 degC design case, with "
     "the same rigour the array work applied: ADR-054 s4 records that EVERY "
     "verified semiconductor there is rated -55 degC (diodes) or -40 degC "
     "(converters) against the -60 degC case, and the LR2021 silicon itself is Top "
     "-40...85 degC / Tmr -55...125 degC (DS 2.2 Tables 3-1/3-2, p.38). A "
     "commercial-grade '-40 degC' thermistor is NOT a -60 degC part - do not "
     "assume the thermistor is exempt from the cold-rating gate. All "
     "TODO(unverified)."),
    ("OPEN-31 SetNtcParams VALUES NOT CHARACTERISED (ADR-058 D4)",
     "The three SetNtcParams inputs are TODO(unverified) and must NOT be invented: "
     "ntc_r_ratio (10 bits with 9 fractional bits, the ratio of the bias resistor "
     "to the NTC at 25 degC), ntc_beta (2 K/lsb) and delay (first-order time delay "
     "coefficient) - DS 2.2 Table 6-70. They must be derived from the POPULATED "
     "part + bias resistor via the datasheet's own identity (RRatio = RNTC/RNTC_25 "
     "= RBiasRatio*(Raw/8192)/(1-Raw/8192); T = Beta/(ln(RRatio)+Beta/298.15) - "
     "273.15). AN1200.106, the datasheet's reference for this maths, is NOT "
     "committed in this repo - obtain it first. A forum figure ('assume 4250 K') is "
     "a bench placeholder, never a characterisation."),
    ("OPEN-32 F33 PA SELF-HEATING vs A NEARBY NTC (ADR-058 D3)",
     "Whether the F33's 2 W PA self-heating perturbs a nearby NTC has NOT been "
     "measured (TODO(unverified)). ADR-058 D3 is the siting RULE that this "
     "open item exists to protect: the NTC must be thermally coupled to the radio's "
     "XTAL / XOSC node and must NOT be sited where a self-heating neighbour "
     "dominates its reading (the F33 PA, the hub converter). The provision on THIS "
     "sheet sits on the bare-module (U3) side, which is why the rule is stated "
     "explicitly rather than left to layout."),
    ("OPEN-33 SX1280 RAIL DECOUPLING PROVISION (ADR-029 2(f), NEW 2026-10-07 R1)",
     "ADR-029 2(f) requires that 'each radio rail gets its own ferrite + bulk "
     "cap from 3V3'. ADR-108 Revision R1 puts the SX1280 supply (U4 pins 1/2) "
     "on the shared +3V3 rail, which settles the NET but not the PROVISION: "
     "no dedicated ferrite bead or bulk capacitor exists for the SX1280 rail "
     "on this sheet, and this revision adds no part. The pin assignment is "
     "closed (OPEN-1); this decoupling provision is registered OPEN rather "
     "than silently omitted, because the SX1280 shares the rail that also "
     "feeds the ESP32-S3 and the F33's logic side, and ADR-029 2(f) exists "
     "precisely so a 2.4 GHz TX burst does not modulate the GNSS LNA or the "
     "ranging front end. WHAT WOULD CLOSE IT: fit the ferrite + bulk cap at "
     "U4 VDD_IN, or record a measurement showing the shared rail is quiet "
     "enough. OWNER: the v9 BOM/placement pass that adds the console "
     "connector (OPEN-10) - the same edit that adds parts at all."),
]


def v9_emit():
    sch_path = V9_OUT_SCH
    libdir = V9_LIBDIR
    fplib = V9_FPLIB
    os.makedirs(libdir, exist_ok=True)
    os.makedirs(fplib, exist_ok=True)

    custom = v9_custom_symbols()
    comps = list(V9_COMPONENTS)

    # ---- ADR-058 / OPEN-7 (2026-10-07): re-home the barometer symbol --------
    # The MS5611 runs in I2C mode on this sheet, so its SDO pad is NOT a data
    # output: the frozen v8j board (SAME Package_LGA:LGA-8_3x5mm_P1.25mm
    # footprint, same I2C mode - its pads 7/8 are I2C_SDA/I2C_SCL exactly as
    # this sheet's U6 pins 7/8) ties pad 6 to GND.  The stock KiCad symbol types
    # that pin `output`, and tying an `output` pin to the GND net - which
    # necessarily carries a PWR_FLAG, i.e. a synthetic `power output` - makes
    # kicad-cli ERC report "Pins of type Output and Power output are connected":
    # an artefact of the synthetic flag, not a wiring defect.  Correcting the
    # TYPE to `passive` is the same class of fix this sheet already applies to
    # the F33 MISO pins (see the F33_MISO net note).  The corrected symbol is
    # RE-HOMED into the project's OWN library (balloon_flight_v9:MS5611_BARO,
    # written to v9_lib/balloon_flight_v9.kicad_sym) so the sheet's cached
    # symbol still matches a library entry - overriding the stock entry in
    # place would raise a lib_symbol_mismatch warning.  Geometry is copied
    # VERBATIM: no pin moves.  NO CONNECTIVITY CHANGES - U6 pin 6 stays on GND.
    _BARO_DST = V9_LIBNAME + ":MS5611_BARO"
    _b = load_lib_symbol("Sensor_Pressure", "MS5611-01BA")
    _m = [m for m in PIN_RE.finditer(_b)
          if m.group(6) == "6" and m.group(1) == "output"]
    if not _m:
        sys.exit("MS5611 SDO pin-type correction: no `output` pin 6 in the "
                 "stock symbol - re-check OPEN-7")
    _mm = _m[0]
    _b = _b[:_mm.start(1)] + "passive" + _b[_mm.end(1):]
    _b = _b.replace('(symbol "Sensor_Pressure:MS5611-01BA"',
                    '(symbol "%s"' % _BARO_DST, 1)
    _b = _b.replace('"MS5611-01BA_0_1"', '"MS5611_BARO_0_1"')
    _b = _b.replace('"MS5611-01BA_1_1"', '"MS5611_BARO_1_1"')
    assert '(symbol "%s"' % _BARO_DST in _b, "baro symbol rename failed"

    # ---- resolve a lib_symbol block for every component -------------------
    lib_blocks = dict(custom)
    lib_blocks[_BARO_DST] = _b
    for (ref, lib_id, value, footprint, dnp, note) in comps:
        if lib_id in lib_blocks:
            continue
        lib, name = lib_id.split(":")
        lib_blocks[lib_id] = load_lib_symbol(lib, name)

    # ---- ADR-058 / OPEN-7 (2026-10-07): the barometer item is a TIE-OFF -------
    # The MS5611 runs in I2C mode on this sheet, so its SDO pad is NOT a data
    # output: the frozen v8j board (SAME LGA-8 3x5 mm footprint, same I2C mode,
    # its pads 7/8 = I2C_SDA/I2C_SCL exactly as here) ties pad 6 to GND.  The
    # stock KiCad symbol types that pin `output`, and tying an `output` pin to
    # the GND net - which necessarily carries a PWR_FLAG, i.e. a synthetic
    # `power output` - makes kicad-cli ERC report "Pins of type Output and Power
    # output are connected".  That is an artefact of the synthetic flag, not a
    # wiring defect, so the pin TYPE is corrected to `passive`: exactly the
    # correction this sheet already applies to the F33 MISO pins for the same
    # class of false pin_to_pin finding (see the F33_MISO net note).  The pin
    # drives nothing here.  NO CONNECTIVITY CHANGES - U6 pin 6 stays on GND.
    # ---- validate: every net endpoint must exist as a symbol pin ----------
    problems = []
    by_ref = {c[0]: c for c in comps}
    for (net, nodes, src) in V9_NETS:
        for (ref, pin) in nodes:
            if ref not in by_ref:
                problems.append("net %s names unknown ref %s" % (net, ref))
                continue
            if pin not in symbol_pins(lib_blocks[by_ref[ref][1]]):
                problems.append("net %s: %s has no pin %s" % (net, ref, pin))
    for (ref, pin, why) in V9_NC:
        if ref not in by_ref:
            problems.append("NC names unknown ref %s" % ref)
        elif pin not in symbol_pins(lib_blocks[by_ref[ref][1]]):
            problems.append("NC: %s has no pin %s" % (ref, pin))
    # a (ref,pin) may belong to exactly ONE net; a duplicate is a silent short
    # (this check exists because the pre-ADR-047 sheet listed R_F1 pin 1 in
    # both +3V3 and VSCAP, which would have shorted the 3V3 rail to the raw
    # 5.4 V cap node).
    owner = {}
    for (net, nodes, src) in V9_NETS:
        for nd in nodes:
            if nd in owner and owner[nd] != net:
                problems.append("pin %s.%s is in TWO nets: %s and %s"
                                % (nd[0], nd[1], owner[nd], net))
            owner[nd] = net
    if problems:
        print("V9 VALIDATION FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(3)

    # ---- footprints: hand the .pretty the fixed F33 + bare + the new SX1280
    # The F33 land pattern is DERIVED AT GENERATION TIME from the vendor's own
    # land file (docs/f33-module/materials/LORA2021F33-2G4 footprint_pads.pcb,
    # via scripts/gen_f33_landpattern.py) instead of being copied out of a
    # custom.pretty file, so a stale or hand-edited copy cannot re-enter the v9
    # design of record.  F33GEN.decode_vendor() raises if the vendor file stops
    # decoding to 18 pads / pitch 3.9289mm / rows on the two 39mm edges, and the
    # coincidence test below fails the build if the emitted pads are not on the
    # vendor land pattern (a pad COUNT match alone is not a geometry match).
    f33_body = F33GEN.footprint_text(V9_LIBNAME, "LoRa2021F33_2G4")
    f33_vendor = F33GEN.decode_vendor()
    f33_hit, f33_near, f33_worst = F33GEN.coincidence(f33_body, f33_vendor["pads"])
    if f33_hit != len(f33_vendor["pads"]):
        sys.exit("v9: F33 footprint is NOT on the vendor land pattern "
                 "(%d/%d pads coincident, nearest %.3f mm, worst %.3f mm)"
                 % (f33_hit, len(f33_vendor["pads"]), f33_near, f33_worst))
    print("F33 land pattern: %s" % F33GEN.describe(F33GEN.signature(f33_body)))
    print("                  %d/%d pads coincident with the vendor land file "
          "(nearest %.3f mm); land size %g x %g mm DERIVED from the "
          "operator-supplied"
          % (f33_hit, len(f33_vendor["pads"]), f33_near,
             F33GEN.LAND_LENGTH_MM, F33GEN.LAND_WIDTH_MM))
    print("                  castellation hole diameter D = %g +/- %g mm "
          "(datasheet s9 p8, read by the operator); land = D + 2*%g mm "
          "solder-fillet margin."
          % (F33GEN.CASTELLATION_D_MM, F33GEN.CASTELLATION_D_TOL_MM,
             F33GEN.LAND_FILLET_MARGIN_MM))
    fp_sources = [
        (None, "LoRa2021F33_2G4", f33_body),
        (os.path.join(V9_SRC_PRETTY, "LoRa2021_Castellated.kicad_mod"),
         "LoRa2021_Castellated", None),
        (V9_SX_FP, "SX1280_QFN24", None),
    ]
    written = []
    for src, leaf, body in fp_sources:
        if body is None:
            if not os.path.exists(src):
                sys.exit("v9: missing footprint source %s" % src)
            body = open(src).read()
        body = re.sub(r'\(footprint\s+"[^"]*"',
                      '(footprint "%s:%s"\n\t\t(version 20250114)\n'
                      '\t\t(generator "pcbnew")\n\t\t(generator_version "9.0")'
                      % (V9_LIBNAME, leaf), body, count=1)
        with open(os.path.join(fplib, leaf + ".kicad_mod"), "w") as fh:
            fh.write(clean(body) + "\n")
        written.append(leaf)
    with open(V9_FPTABLE, "w") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "Tracker_Mechanical")'
                 '(type "KiCad")(uri "${KIPRJMOD}/../../footprints/'
                 'tracker_mechanical.pretty")(options "")(descr "Repo-local '
                 'mechanical footprints for the v9 hub/wing assembly; holds the '
                 'real hub-side wing socket land set Wing_Tab_4P - ADR-048"))'
                 '\n\t(lib (name "%s")'
                 '(type "KiCad")(uri "${KIPRJMOD}/v9_lib/%s.pretty")'
                 '(options "")(descr "v9 flight board footprints: fixed F33 '
                 'land pattern (d5a2e47) + bare LoRa2021 + SX1280 (UNVERIFIED) + '
                 'Wing_Tab_4P"))'
                 '\n)\n' % (V9_LIBNAME, V9_LIBNAME))

    # ---- placement: one component per grid slot, columns left to right ----
    V9_COLUMNS = [
        ["U5", "U6", "U7"],
        ["U1"],
        ["U2"],
        ["U3"],
        ["U4"],
        ["J_VCC", "C_BULK", "C_HF", "D_CLAMP", "R_MON1", "R_MON2", "C_MON"],
        ["C_CAP1", "C_CAP2", "R_BAL1", "R_BAL2", "D1", "R_DIV1", "R_DIV2",
         "R_F1", "C4"],
        ["ANT1", "ANT2", "ANT3", "ANT4"],
        # ADR-048: the FOUR wing-mount interfaces (one per hub edge, 90 deg
        # apart) and their four DNP bypass Schottky provisions.  Each J_W<n> is
        # drawn as one 4-pad socket land set; the series-stack links between
        # adjacent interfaces are the hub-link nets of ADR-046 s2.3.
        ["J_W1", "J_W2", "J_W3", "J_W4",
         "D_BP1", "D_BP2", "D_BP3", "D_BP4"],
        # ADR-051: the INDEPENDENT hub-array string (its own cells, its own
        # converter input) and the four per-wing latched cut channels.  Appended
        # LAST on purpose: col_x accumulates left-to-right, so appending a column
        # moves no already-placed component.
        ["PVA%d" % _hci for _hci in range(1, V9_HUB_ARRAY_CELLS + 1)]
        + ["D_HUB%d" % _hci for _hci in range(1, V9_HUB_ARRAY_CELLS + 1)]
        + ["U_HUB_CVT"] + ["U_CUT%d" % _hci for _hci in range(1, 5)],
        # ADR-058: the on-chip NTC temperature-compensation provision (both parts
        # DNP).  Appended LAST for the same reason as the hub column above:
        # col_x accumulates left-to-right, so a new trailing column moves no
        # already-placed component.
        ["R_NTC1", "TH_NTC1"],
    ]
    V9_COL_TITLES = [
        "GNSS / BARO / POWER",
        "U1 ESP32-S3-WROOM-1U-N8R8",
        "U2 LoRa2021F33-2G4  (433 MHz TX) - VCC PRE-LDO, ADR-047",
        "U3 bare LoRa2021  (2.4 GHz RX)",
        "U4 SX1280  (2.4 GHz ranging) - REAL pinout, OPEN-13 closed 2026-10-14; "
        "wiring rebuilt 2026-10-15",
        "F33 RAIL PROVISION (ADR-047): pin-1 selector / bulk / clamp / monitor",
        "SUPERCAP BANK (SERIES + BALANCING) / BAT54 / DIVIDER / GNSS RC",
        "U.FL ANTENNAS (4 feeds: ANT1 433 TX / ANT2 2.4 ranging / ANT3 2.4 RX "
        "/ ANT4 GNSS L1) - ADR-108 Revision R1",
        "FOUR WING INTERFACES at 90 deg (ADR-046 / ADR-048): 4 lands per face x "
        "2 faces = 8 lands each, 4.0 x 1.2 mm, pitch 1.8 mm; 1 SOLAR_P / 2 GND / "
        "3 RF = CUT_SENSE_W<n> (ADR-051 s2.6) / 4 SOLAR_N + 4 POPULATED bypass "
        "Schottky (SS24, 2 A / 40 V)",
        "INDEPENDENT HUB ARRAY (ADR-051 s2.1) + 4 LATCHED CUT CHANNELS (s2.5/s2.6)",
        "LR2021 ON-CHIP NTC TEMP-COMP PROVISION (ADR-058) - R_NTC1 + TH_NTC1, "
        "BOTH DNP: the chip's NTC sense pin (chip pin 3) is NOT broken out on the "
        "owned bare NiceRF module (OPEN-29 / ADR-058 D6)",
    ]
    placed_refs = [r for col in V9_COLUMNS for r in col]
    missing = [c[0] for c in comps if c[0] not in placed_refs]
    if missing:
        sys.exit("v9 layout missing refs: %s" % missing)

    sizes = {}
    for c in comps:
        x0, y0, x1, y1 = symbol_extent(lib_blocks[c[1]])
        sizes[c[0]] = (x1 - x0, y1 - y0)
    col_x, x = [], 30.48
    for col in V9_COLUMNS:
        col_x.append(x)
        x += max(sizes[r][0] for r in col) + 45.72
    pos = {}
    y_bottom = 0.0
    for ci, col in enumerate(V9_COLUMNS):
        y = 50.8
        for ref in col:
            pos[ref] = (round(col_x[ci] / 1.27) * 1.27, round(y / 1.27) * 1.27)
            y += sizes[ref][1] + 25.4
        y_bottom = max(y_bottom, y)

    # ---- body ------------------------------------------------------------
    body = ['\t(text "BALLOON v9 TRI-BAND FLIGHT BOARD - DESIGN-INTENT '
            'schematic from the v9 decision records (ADR-029/034/035/036-043, '
            'ADR-044/044a/045/046/047/048/049/050/051/052/053/054). NOT derived from a PCB."\n\t\t(exclude_from_sim no)\n'
            '\t\t(at 30.48 20.32 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
            '(size 2.54 2.54)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n'
            '\t\t(uuid "%s")\n\t)' % uid(),
            '\t(text "ADR-047 (operator directive 2026-10-07): F33 pin 1 VCC is '
            'provisioned for the MODULE MAXIMUM DRAW (1118 mA @ 5.5 V = 6.15 W DC) '
            'and is fed from the RAW supercap node (VSCAP, post-BAT54, PRE-LDO) '
            'through the ADR-029 D8 pin-1 selector J_VCC. It is NEVER fed through '
            'the TPS7A02 (<=300 mA vs 1118 mA = hard failure). Local bulk C_BULK + '
            'C_HF, clamp D_CLAMP, rail monitor R_MON1/R_MON2/C_MON -> IO13. '
            'Full +33 dBm needs >=5.0 V rail; +30 dBm needs >=3.54 V interpolated '
            '(ADR-044 S8 table). Firmware must gate TX on the LOADED rail."\n'
            '\t\t(exclude_from_sim no)\n\t\t(at 30.48 24.13 0)\n\t\t(effects\n'
            '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),
            '\t(text "ADR-046 + ADR-048 (wing interface, Status PROPOSED - not '
            'human-accepted): the v9 hub carries FOUR wing-mount interfaces at '
            '90 deg spacing, J_W1..J_W4. Each is one socket land set: 4 copper '
            'lands per face on BOTH outer layers = 8 lands per interface, land '
            '4.0 x 1.2 mm, pitch 1.8 mm, insertion depth 6.0 mm. Net order 1 '
            'SOLAR_P / 2 GND / 3 RF_FEED (v9 provision, NO NET) / 4 SOLAR_N. '
            'Series stack wired on the hub: W1_P -> BAT54 (D1) -> supercap; '
            'W1_N == W2_P, W2_N == W3_P, W3_N == W4_P (hub links); W4_N = stack '
            'bottom = GND. Each interface GND land ties to the hub ground plane. '
            'One POPULATED bypass Schottky per interface (D_BP1..D_BP4, SS24 = 2 A / 40 V on an SMA land) across '
            'W<n>_SOLAR_P (K) - W<n>_SOLAR_N (A). Geometry lives in the real '
            'footprint Tracker_Mechanical:Wing_Tab_4P. ADR-048 D-1: the socket '
            'spec s2/s4 say >= 0.5 mm copper-to-edge clearance, ADR-046 s2.2 '
            'says >= 1.0 mm and the ADR number is implemented. OPEN-20/21/22/23/24 '
            'hold the open questions; see REPORT.md. ADR-051 s2.1 adds the INDEPENDENT hub array: its OWN nets (HUB_PV_P / HUB_PV_MID<n> / HUB_PV_N) and its OWN converter input, never in series with and never a tap on the wing chain (the only shared node is GND). ADR-051 s2.6 nets interface pin 3 (RF_FEED) as CUT_SENSE_W<n>; ADR-051 s2.5 gives one LATCHED one-shot cut driver per wing. See the ADR-051/053/054 notes below."\n'
            '\t\t(exclude_from_sim no)\n\t\t(at 30.48 26.67 0)\n\t\t(effects\n'
            '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),
            '\t(text "ADR-051 s2.7 / ADR-054 s2.2+s3.2 - THE PER-INTERFACE BYPASS DIODES ARE POPULATED AND RE-RATED, AND THEY SIT HUB-SIDE. D_BP1..D_BP4 bridge each wing interface (W<n>_SOLAR_P cathode -> W<n>_SOLAR_N anode) and are now SS24 = 2 A / 40 V on an SMA land, not DNP BAT54 = 200 mA / 30 V on SOD-323. WHY HUB-SIDE: a cut jettisons the wing AND every part soldered to it, so only a HUB-side diode can bridge the gap the cut leaves; a wing-board diode leaves with the wing and the array delivers 0.00 W on the first cut. WHY 2 A / 40 V: after a cut the remaining wings drive the array FULL 1.2 A through that diode CONTINUOUSLY for the rest of the flight - a permanent-continuous bypass duty, not a shading transient - so 200 mA is disqualified, and 30 V cannot clear the ~9.58 V cold open-circuit stack. SOD-323 cannot carry 2 A, hence SMA."\n\t\t(exclude_from_sim no)\n\t\t(at 30.48 29.21 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),
            '\t(text "ADR-051 s2.1 - THE HUB ARRAY IS AN INDEPENDENT SERIES STRING. It has its OWN nets (HUB_PV_P positive, HUB_PV_MID<n> interior, HUB_PV_N negative) and its OWN converter/harvester input (U_HUB_CVT), and it is NEVER in series with, and never a tap on, the wing chain - the ONLY node it may share with the wing system is GND, and only through the converter\'s ground pin. If it were wired into the wing chain the FIRST wing cut would remove the hub array\'s path together with the wing\'s cells and the cut would become suicide. scripts/hub_array_topology_check.py enforces this mechanically. *** CELL COUNT IS A DOCUMENTED PLACEHOLDER *** (currently 2 cells; ADR-051 s2.2 recommends H2 = 2, H3 = 3 is the fallback) - the count, the mounting plane, the harvester part and the hub OUTLINE are all OPEN (OPEN-26)."\n\t\t(exclude_from_sim no)\n\t\t(at 30.48 30.48 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),
            '\t(text "ADR-051 s2.5 decision item 5 - THE CUT DRIVE MUST BE A LATCHED ONE-SHOT, one per wing (U_CUT1..U_CUT4). Cutting is IRREVERSIBLE, and a level-sensitive driver can RE-FIRE an already-fired channel on a reset, a brown-out, a firmware retry or a floating gate - each fire costing ~2.59 J of the bank\'s 16.63 J usable energy at the exact moment the bank matters (ADR-051 s2.5.1). The mandate: a firmware one-shot with a persistent NVS fired flag per channel PLUS a hardware series gate that requires an explicit arming sequence, so no single event can fire a channel twice. Firmware must also serialise cuts - 4 simultaneous fires draw 9.9 A = 2.4x the IRLML2502 class rating - require the bank above ~3.3 V, cap the on-time (<=193 ms / <=3.33 J) and LOG a cut that silently fails. The exact part and the latch topology are TODO(unverified) (OPEN-28)."\n\t\t(exclude_from_sim no)\n\t\t(at 30.48 31.75 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),
            '\t(text "ADR-051 s2.6 - THE RESERVED RF_FEED LAND IS NOW THE PER-WING CUT-SENSE / CUTTER LINE. J_W<n> pad 3 carries CUT_SENSE_W<n>, which does the nichrome cutter drive AND the continuity sense on ONE conductor plus the shared ground - four independently controllable cutters at ZERO connector cost, because the land and the position were already paid for. Netting it closes the four pin_not_connected ERC errors an unnetted provision produced. HONEST CAVEAT (ADR-051 s2.6 + s4 item 9): on the v9 WING, RF_FEED is a copper land with NO net, so the continuity measurement only becomes meaningful after a wing re-spin ties RF_FEED into the cut loop\'s return. The GPIO/divider assignment is OPEN (OPEN-25). The \'do not tie it to GND\' prohibition of ADR-046 s2.4 STANDS."\n\t\t(exclude_from_sim no)\n\t\t(at 30.48 33.02 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),]
    for ci, title in enumerate(V9_COL_TITLES):
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s 43.18 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
                    '(size 1.524 1.524)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                    '\t\t)\n\t\t(uuid "%s")\n\t)'
                    % (title, fmt(round(col_x[ci] / 1.27) * 1.27), uid()))

    todo_x = 30.48
    # start the TODO block clear of the deepest component column (ADR-047 added
    # a new column and two more parts to the supercap column)
    todo_y = round((y_bottom + 10.16) / 1.27) * 1.27
    for (title, txt) in V9_TODO:
        body.append('\t(text "TODO(unverified) %s -- %s"\n'
                    '\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n'
                    '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n'
                    '\t\t(uuid "%s")\n\t)' % (title, txt, fmt(todo_x),
                                              fmt(todo_y), uid()))
        todo_y += 3.81

    net_of = {}
    net_src = {}
    for (net, nodes, src) in V9_NETS:
        net_src[net] = src
        for nd in nodes:
            net_of[nd] = net
    nc_of = {(r, p): why for (r, p, why) in V9_NC}

    power_syms, wires, labels, ncs, notes = [], [], [], [], []
    stats = dict(pins=0, nets=set(), labels=0, power=0, nc=0, todo=0,
                 power_out=set())

    for (ref, lib_id, value, footprint, dnp, note) in comps:
        block = lib_blocks[lib_id]
        sx, sy = pos[ref]
        pins = symbol_pins(block)
        pin_txt = "".join('\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n' % (n, uid())
                          for n in sorted(pins, key=lambda k: (len(k), k)))
        body.append(
            "\t(symbol\n\t\t(lib_id \"%s\")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n"
            "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
            "\t\t(dnp %s)\n\t\t(uuid \"%s\")\n"
            "\t\t(property \"Reference\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Value\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Footprint\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
            "%s\t\t(instances\n\t\t\t(project \"%s\"\n"
            "\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference \"%s\")\n"
            "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n"
            % (lib_id, fmt(sx), fmt(sy), "no" if not dnp else "yes", uid(),
               ref, fmt(sx + 2.54), fmt(sy - 7.62), value, fmt(sx + 2.54),
               fmt(sy + 2.54), footprint, fmt(sx), fmt(sy), pin_txt,
               V9_PROJECT, uid(), ref))

        for pnum in sorted(pins, key=lambda k: (len(k), k)):
            pin = pins[pnum]
            px, py = pin_point(sx, sy, pin)
            stats["pins"] += 1
            key = (ref, pnum)
            if key in net_of:
                net = net_of[key]
                ex, ey = stub_end(sx, sy, pin, 5.08)
                wires.append((px, py, ex, ey))
                if net in ("+3V3", "GND"):
                    power_syms.append((net, ex, ey))
                    stats["power"] += 1
                else:
                    labels.append((net, ex, ey))
                    stats["labels"] += 1
                stats["nets"].add(net)
                if pin["type"] == "power_out":
                    stats["power_out"].add(net)
            elif key in nc_of:
                ncs.append((px, py))
                stats["nc"] += 1
            # else: deliberately left floating; covered by a V9_TODO note

    # PWR_FLAG on every rail not driven by a real power-output pin
    flag_pts = {}
    for (net, x, y) in power_syms:
        flag_pts.setdefault(net, (x, y))
    for (net, x, y) in labels:
        flag_pts.setdefault(net, (x, y))
    flag_nets = {n for (n, _, _) in power_syms} - stats["power_out"]
    from_lab = {n for (n, _, _) in labels}
    flag_nets |= {n for n in from_lab if n.startswith("V") or n == "SOLAR_IN"}
    # ADR-047: any net that carries a power_in pin but has no power_out and no
    # PWR_FLAG would raise "power pin not driven". F33_VCC (U2 pin 1, the 2 W PA)
    # and GNSS_VCC (U5 pin 8) are such nets: declare each as a source.
    pin_type = {}
    for (ref, lib_id, value, footprint, dnp, note) in comps:
        for pn, pin in symbol_pins(lib_blocks[lib_id]).items():
            pin_type[(ref, pn)] = pin["type"]
    power_in_nets = {net for (net, nodes, src) in V9_NETS
                     if any(pin_type.get(nd) == "power_in" for nd in nodes)}
    flag_nets |= power_in_nets - stats["power_out"]
    flags = []
    # ADR-047: the old fixed "+5.08 in x" flag offset is unsafe on this sheet -
    # U5's pins sit 2.54 mm apart on one horizontal line, so a flag stub landed
    # exactly on the neighbouring pin's +3V3 symbol and MERGED GNSS_VCC into 3V3
    # (ERC multiple_net_names + a bogus pin_to_pin). Place each flag stub on the
    # first candidate direction whose target point is free and whose segment
    # passes through no existing endpoint/label/power-symbol point.
    occ = set()
    for (net, x, y) in power_syms:
        occ.add((round(x, 2), round(y, 2)))
    for (txt, x, y) in labels:
        occ.add((round(x, 2), round(y, 2)))
    for (x1, y1, x2, y2) in wires:
        occ.add((round(x1, 2), round(y1, 2)))
        occ.add((round(x2, 2), round(y2, 2)))

    def flag_offset(fx, fy):
        fx, fy = round(fx, 2), round(fy, 2)
        for dx, dy in ((-5.08, 0), (-7.62, 0), (-10.16, 0), (-12.7, 0),
                       (5.08, 0), (7.62, 0), (10.16, 0), (12.7, 0),
                       (0, -5.08), (0, -7.62), (0, -10.16),
                       (0, 5.08), (0, 7.62), (0, 10.16)):
            tx, ty = round(fx + dx, 2), round(fy + dy, 2)
            if (tx, ty) in occ:
                continue
            clash = False
            if dy == 0:
                lo, hi = sorted((fx, tx))
                clash = any(oy == fy and lo < ox < hi for (ox, oy) in occ)
            else:
                lo, hi = sorted((fy, ty))
                clash = any(ox == fx and lo < oy < hi for (ox, oy) in occ)
            if not clash:
                return dx, dy
        return None

    for net in sorted(flag_nets):
        if net not in flag_pts:
            continue
        x, y = flag_pts[net]
        off = flag_offset(x, y)
        if off is None:
            sys.exit("v9: no free PWR_FLAG stub direction for net %s at (%s, %s)"
                     % (net, fmt(x), fmt(y)))
        dx, dy = off
        wires.append((x, y, x + dx, y + dy))
        occ.add((round(x + dx, 2), round(y + dy, 2)))
        flags.append((net, x + dx, y + dy))

    for (x1, y1, x2, y2) in wires:
        body.append('\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
                    '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
                    '\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x1), fmt(y1), fmt(x2), fmt(y2), uid()))
    for (txt, x, y) in labels:
        body.append('\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n'
                    '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (txt, fmt(x), fmt(y), uid()))

    for i, (net, x, y) in enumerate(power_syms):
        pref = "#PWR0%03d" % (i + 1)
        body.append(('\t(symbol\n\t\t(lib_id "power:%s")\n\t\t(at %s %s 0)\n'
                     '\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                     '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                     '\t\t(property "Reference" "#PWR"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Value" "%s"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                     '\t\t(instances\n\t\t\t(project "%s"\n'
                     '\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference "#PWR")\n'
                     '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                     % (net, fmt(x), fmt(y), uid(), fmt(x + 2.54),
                        fmt(y + 2.54), net, fmt(x + 2.54), fmt(y - 2.54),
                        fmt(x), fmt(y), uid(), V9_PROJECT, uid()))
                     .replace('#PWR', pref))
    for i, (net, x, y) in enumerate(flags):
        body.append(('\t(symbol\n\t\t(lib_id "power:PWR_FLAG")\n'
                     '\t\t(at %s %s 0)\n\t\t(unit 1)\n'
                     '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                     '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                     '\t\t(property "Reference" "#FLG0%d"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Value" "PWR_FLAG"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                     '\t\t(instances\n\t\t\t(project "%s"\n'
                     '\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference "#FLG0%d")\n'
                     '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                     % (fmt(x), fmt(y), uid(), i + 1, fmt(x + 2.54),
                        fmt(y + 2.54), fmt(x + 2.54), fmt(y - 2.54),
                        fmt(x), fmt(y), uid(), V9_PROJECT, uid(), i + 1)))
    for (x, y) in ncs:
        body.append('\t(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x), fmt(y), uid()))

    # power symbol definitions used
    for net in sorted({n for (n, _, _) in power_syms}):
        key = "power:" + net
        if key not in lib_blocks:
            lib_blocks[key] = load_lib_symbol("power", net)
    if flags:
        lib_blocks["power:PWR_FLAG"] = load_lib_symbol("power", "PWR_FLAG")

    libdefs = "\n".join(lib_blocks[k] for k in lib_blocks)
    sch = ('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n'
           '\t(generator_version "9.0")\n\t(uuid "%s")\n\t(paper "A2")\n'
           '\t(title_block\n\t\t(title "Balloon v9 Tri-Band Flight Board")\n'
           '\t\t(date "2026-10-07")\n\t\t(rev "v9-design-intent")\n'
           '\t\t(company "Balloon Relay")\n'
           '\t\t(comment 1 "DESIGN-INTENT schematic derived from ADR-029/034/035/'
           '036-045. Uncited pins carry TODO(unverified) notes; nothing guessed.")\n'
           '\t)\n\t(lib_symbols\n%s\n\t)\n%s'
           '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n)\n'
           % (uid(), libdefs, "".join(body)))
    with open(sch_path, "w") as fh:
        fh.write(clean(sch))

    # standalone symbol library
    with open(V9_SYMLIB, "w") as fh:
        fh.write('(kicad_symbol_lib\n\t(version 20241209)\n'
                 '\t(generator "kicad_symbol_editor")\n'
                 '\t(generator_version "9.0")\n')
        for k, blk in lib_blocks.items():
            if k.startswith(V9_LIBNAME + ":"):
                fh.write("\t" + blk.replace('(symbol "%s:' % V9_LIBNAME,
                                            '(symbol "', 1) + "\n")
        fh.write(")\n")

    # project file: kicad-cli only resolves the PROJECT-LOCAL library tables when
    # a matching <name>.kicad_pro exists next to the schematic.
    pro_src = os.path.join(HERE, "v_c3_flight.kicad_pro")
    if os.path.exists(pro_src):
        pro = open(pro_src).read().replace("v_c3_flight", V9_PROJECT)
        with open(os.path.join(HERE, V9_PROJECT + ".kicad_pro"), "w") as fh:
            fh.write(pro)

    # KiCad-convention shared tables (union of the C3 + v9 libraries) so that
    # either generator leaves the other's libs resolvable.
    union = sorted({k.split(":")[0] for k in lib_blocks}
                   | {"balloon_flight", "Sensor_Pressure", "Diode"})
    # MERGED, not rewritten: the v10 target writes its rows into these same
    # shared tables.  Rewriting here would strip balloon_flight_v10 and make
    # the v10 sheet ERC with `does not include the symbol library` warnings.
    v9_sym_entries = []
    for lib in union:
        uri = (os.path.join(SYMDIR, lib + ".kicad_sym")
               if lib not in ("balloon_flight", V9_LIBNAME)
               else ("${KIPRJMOD}/balloon_flight.kicad_sym"
                     if lib == "balloon_flight"
                     else "${KIPRJMOD}/v9_lib/%s.kicad_sym" % V9_LIBNAME))
        v9_sym_entries.append((lib, uri, ""))
    merge_lib_table(OUT_LIBTABLE, "sym_lib_table", v9_sym_entries)
    merge_lib_table(OUT_FPTABLE, "fp_lib_table", [
        ("balloon_flight", "${KIPRJMOD}/balloon_flight.pretty",
         "Flight board footprints exported from the frozen PCB"),
        # ADR-048: the repo's own mechanical library, so the wing socket land
        # set resolves in the v9 project without reusing a generic pin-header
        # footprint.
        ("Tracker_Mechanical",
         "${KIPRJMOD}/../../footprints/tracker_mechanical.pretty",
         "Repo-local mechanical footprints for the v9 hub/wing assembly; holds "
         "the real hub-side wing socket land set Wing_Tab_4P - ADR-046/ADR-048"),
        (V9_LIBNAME, "${KIPRJMOD}/v9_lib/%s.pretty" % V9_LIBNAME,
         "v9 flight board footprints"),
    ])

    libs = sorted({k.split(":")[0] for k in lib_blocks})
    with open(V9_SYMTABLE, "w") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n')
        for lib in libs:
            uri = (os.path.join(SYMDIR, lib + ".kicad_sym")
                   if lib != V9_LIBNAME
                   else "${KIPRJMOD}/v9_lib/%s.kicad_sym" % V9_LIBNAME)
            fh.write('\t(lib (name "%s")(type "KiCad")(uri "%s")(options "")'
                     '(descr ""))\n' % (lib, uri))
        fh.write(")\n")

    stats["comp"] = len(comps)
    stats["fp"] = written
    return stats


def main_v9():
    print("v9 schematic variant (design-intent, NOT derived from a PCB)")
    print("records  : ADR-029, docs/adr/108-f33-sx1280-pin-plan.md, ADR-034,")
    print("           ADR-035, ADR-036-045, docs/DUAL-VARIANT-DESIGN.md,")
    print("           docs/V9-RADIO-SITE-MATRIX.md,")
    print("           ADR-044 (power rails) + ADR-047 (F33 max-draw provisioning),")
    print("           ADR-046 (wing tab/socket) + ADR-048 (v9 hub wing interfaces),")
    print("           frozen v8i netlist tracker/hardware/output/v8i_krt_gnss.kicad_pcb")
    stats = v9_emit()
    print("components    :", stats["comp"])
    print("symbol pins   :", stats["pins"])
    print("net labels    :", stats["labels"])
    print("power pins    :", stats["power"])
    print("no_connect    :", stats["nc"])
    print("TODO(unverified) notes:", len(V9_TODO))
    print("distinct nets :", len(stats["nets"]), sorted(stats["nets"]))
    print("footprints    :", stats["fp"])
    print("wrote         :", V9_OUT_SCH)
    print("                ", V9_SYMLIB)
    print("                ", V9_FPLIB)


# =====================================================================
# v10 FLIGHT BOARD -- DESIGN-INTENT schematic (ADR-128).
#
# The DIRECTION OF TRUTH is INVERTED with respect to the C3 generator at the
# top of this file.  The C3 sheet MIRRORS a frozen PCB.  The v10 sheet is built
# from the CONNECTIVITY REGISTRY,
#
#     tracker/hardware/connectivity/v10_pinmap.reg
#
# which is the source of truth for which physical pad carries which net.  Every
# net below is read out of that file at generation time; parse_pcb() is
# deliberately NEVER called anywhere in this section.  hub_board_v10.kicad_pcb is
# a BUILD PRODUCT of the registry, so check_schematic_parity.py reading the
# board back is a CHECK on the registry, never an author of it.
#
# Registry line format:   REF.PIN  NET  # authority
# `UNASSIGNED` = the pin has no net; connectivity/OPEN-ITEMS.md records why.
# Those pins are collected into V10_NC and NEVER turned into a net.
#
# Reference designators adopted from v9 unchanged (ADR-119):
#   U1    ESP32-S3-WROOM-1U-N8R8     MCU
#   U2    LoRa2021F33-2G4            433 MHz TX                (site A)
#   U3    LoRa2021_Castellated       2.4 GHz RX                (site B)
#   U_C   LoRa2021_Castellated       2.4 GHz                   (site C, ADR-119)
#   U_E28 E28-2G4M27SX               2.4 GHz ranging           (site D, ADR-118)
#   U5    MAX-M10S                   GNSS L1
#   U6    MS5611-01BA                barometer (I2C)
#   U7    TPS7A02                    3.3 V LDO (ADR-006)
#   C_CAP1 / C_CAP2                  supercap bank
#   J_PROG                           6-pin programming / USB header (ADR-121)
#   J_W1..J_W4                       hub wing sockets (ADR-046 / ADR-048)
#   ANT1..ANT4                       U.FL feeds
# =====================================================================

V10_OUT_SCH = os.path.join(HERE, "v10_flight.kicad_sch")
V10_LIBDIR = os.path.join(HERE, "v10_lib")
V10_FPLIB = os.path.join(V10_LIBDIR, "balloon_flight_v10.pretty")
V10_SYMLIB = os.path.join(V10_LIBDIR, "balloon_flight_v10.kicad_sym")
V10_FPTABLE = os.path.join(HERE, "v10_fp-lib-table")
V10_SYMTABLE = os.path.join(HERE, "v10_sym-lib-table")
V10_PROJECT = "v10_flight"
V10_LIBNAME = "balloon_flight_v10"
V10_REG = os.path.join(REPO, "tracker", "hardware", "connectivity",
                       "v10_pinmap.reg")
V10_E28_FP = os.path.join(REPO, "tracker", "hardware", "footprints", "e28",
                          "E28-2G4M27SX.kicad_mod")
# ADR-139 replacement part. The BOARD carries this footprint as `NiceRF:LoRa1280` (set by
# swap_u_e28_to_lora1280.py); the SCHEMATIC copies it into the generated
# balloon_flight_v10 library like every other v10 part, because that is the only fp library the
# v10 sheet's fp-lib-table declares. Pointing the symbol at `NiceRF:LoRa1280` instead produces
# an ERC `footprint_link_issues` on U_LORA1280 (measured 2026-11-02), which is a library-table
# problem, not a design problem.
V10_LORA1280_FP = os.path.join(REPO, "tracker", "hardware", "footprints", "lora1280",
                               "LoRa1280.kicad_mod")

# Tokens the registry uses for "this pin has no net".
V10_NETLESS_TOKENS = ("NC", "UNASSIGNED", "-", "N/A", "NONE")

# --- E28-2G4M27SX (Ebyte): SX1280 + PA + LNA + RF switch, 16 castellated
# pads.  AUTHORITATIVE PIN MAP, from the sidecar derivation record
# tracker/hardware/footprints/e28/E28-2G4M27SX.md (its "Pin map (datasheet ch.3
# table)" section), which transcribes
# docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.0.pdf (Ebyte, Rev 1.0,
# 2021-11-15) chapter 3, read via a vision pass over the rendered page.
# Pads 8 (RX_EN, LNA enable, active high) and 9 (TX_EN, PA enable, active high)
# are NEW versus the bare SX1280 and are registered UNASSIGNED - see
# connectivity/OPEN-ITEMS.md OPEN-E28-EN.  They are NOT guessed here; leaving
# a PA/LNA enable unasserted is a wiring decision, not a schematic default.
V10_LORA1280_PINS = [
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
]

# --- U_HUB_CVT: the hub array's OWN converter / harvester input provision
# (ADR-051 s2.1 decision 1).  Footprint Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm
# _EP1.1x1.1mm; only pins 1/2/3 are netted (HUB_PV_P / GND / HUB_PV_N), every
# other pin of the land pattern is UNASSIGNED in the registry.  The pins are
# drawn anyway so the unassigned pads are VISIBLE on the sheet, which is the
# whole point of ADR-128: an open question must be legible, not hidden.
V10_HUB_CVT_PINS = (
    [("1", "PV_P", "passive"), ("2", "GND", "power_in"),
     ("3", "PV_N", "passive")]
    + [("%d" % _p, "NC%d" % _p, "passive") for _p in range(4, 17)]
    + [("17", "EP", "passive")])


def v10_read_registry(path=None):
    """Parse the v10 connectivity registry.  Returns (nets, netless).

      nets : [(net, [(ref, pin), ...], source_note), ...]   sorted by net name
      netless : [(ref, pin, authority), ...]                in file order

    This is the ONLY place v10 connectivity enters the generator.  `UNASSIGNED`
    rows never become nets - they are the board's recorded open questions.
    """
    path = path or V10_REG
    buckets, sources, netless = {}, {}, []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2 or "." not in parts[0]:
                continue
            ref, pin = parts[0].split(".", 1)
            net = parts[1]
            authority = " ".join(parts[2:]).strip()
            if authority.startswith("#"):
                authority = authority[1:].strip()
            if pin == '""':              # the module shield / exposed pad
                pin = ""
            if net.upper() in V10_NETLESS_TOKENS:
                netless.append((ref, pin, authority))
                continue
            buckets.setdefault(net, []).append((ref, pin))
            sources.setdefault(net, set()).add(authority)
    nets = []
    for net in sorted(buckets):
        nodes = sorted(set(buckets[net]),
                       key=lambda rp: (rp[0], int(rp[1]) if rp[1].isdigit()
                                       else 1 << 30, rp[1]))
        nets.append((net, nodes, "; ".join(sorted(sources[net]))))
    return nets, netless


# Nets + open pins, straight out of the registry.
# Import-safe: check_sch_gates.py imports this module for the C3 path, so a
# missing registry must not explode at import time (it will instead fail loudly
# in v10_emit(), where the v10 target is actually asked for).
if os.path.exists(V10_REG):
    V10_NETS, V10_NC = v10_read_registry()
else:
    V10_NETS, V10_NC = [], []
# V10_NC is the sheet's explicit no-connect list: exactly the UNASSIGNED rows,
# nothing added and nothing dropped.  It is bound HERE rather than aliased from
# the token tuple below -- the two used to share one name, so a second
# v10_read_registry() call inside one process silently reclassified every
# UNASSIGNED pin as a real net (the tokens had been overwritten by the parsed
# rows).  Keep the names disjoint.

# NOTE ON THE INSTANCE PATH (v9_emit's style, reproduced on purpose).
# Every placed symbol gets its OWN uid() as its `(path ...)`, exactly as
# v9_emit() does - it is NOT the sheet root uuid.  This is load-bearing, not an
# oversight: measured on this host (kicad-cli 9.0.9), KiCad only synthesises
# `unconnected-(REF-PINNAME-PadN)` placeholder nets when the instance path
# RESOLVES to the sheet root.  Those placeholder nets are KiCad's, not declared
# connectivity, and check_schematic_parity.py's G3 counts them as schematic-only
# nets (39 of them on this sheet, one per UNASSIGNED pin).  Emitting the sheet in
# the v9 style makes the exporter report exactly the nets the sheet declares,
# which is what G3 is meant to compare - and it keeps v10 readable by the same
# gate, in the same way, as the v9 sheet it succeeds.
def inst_path():
    return uid()

# Land numbers a symbol expresses differently from the registry.  The registry
# addresses the exposed pad as `REF.""` (that is what the .kicad_pcb pad is
# literally called); a symbol cannot have an empty pin number, so the EP is
# drawn as the conventional pad 17.  Mapped explicitly rather than silently
# dropped: an UNASSIGNED pin the sheet cannot show would be invisible.
V10_PIN_ALIAS = {("U_HUB_CVT", ""): "17"}

# --- component table -------------------------------------------------------
# ref, lib_id, value, footprint, dnp, note.
# Symbol pin tables are REUSED verbatim from v9 wherever the part is unchanged
# (V9_F33_PINS for U2, V9_BARE_PINS for U3 and U_C, V9_TPS7A02_PINS for U7);
# only the parts v10 ADDS get new tables (E28, the 17-land hub converter).
V10_COMPONENTS = [
    ("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1U-N8R8",
     "RF_Module:ESP32-S3-WROOM-1U", False,
     "ADR-029 D1 / ADR-037 D1: octal-PSRAM -N8R8, U.FL variant. 41 pins; "
     "pin 15/16/26..30/35 and the shield land are UNASSIGNED "
     "(connectivity/OPEN-ITEMS.md)."),
    ("U2", "balloon_flight_v10:F33_2G4", "LoRa2021F33-2G4",
     "balloon_flight_v9:LoRa2021F33_2G4", False,
     "ADR-034 D1/D2 + ADR-040 D1: 433 MHz TX on the 2 W sub-GHz port "
     "(pin 9). Pin table reused from v9 unchanged."),
    ("U3", "balloon_flight_v10:LR2021_BARE", "LoRa2021_Castellated",
     "balloon_flight_v9:LoRa2021_Castellated", False,
     "ADR-034 D1: separate bare LoRa2021 = the 2.4 GHz RX chip. "
     "Pin table reused from v9 unchanged."),
    ("U_C", "balloon_flight_v10:LR2021_BARE", "LoRa2021_Castellated",
     "balloon_flight_v9:LoRa2021_Castellated", False,
     "ADR-119 site C: a THIRD bare LoRa2021 on the same castellated land. "
     "Identical part to U3, so it REUSES the v9 U3 symbol (per ADR-128 task "
     "note); only its per-site control nets differ (/U_C_CS_N, /U_C_BUSY, "
     "/U_C_RESET_N, /U_C_IRQ) - see ADR-119."),
    ("U_LORA1280", "balloon_flight_v10:LoRa1280", "LoRa1280",
     "balloon_flight_v10:LoRa1280", False,
     "ADR-139: G-NiceRF LoRa1280 (SX1280, 12.5 dBm, ranging: YES) replaced the "
     "E28-2G4M27SX at site D. The E28's PA/LNA enables (8/9) do not exist on "
     "this part, which CLOSES OPEN-E28-EN rather than waiving it. Pin 9 is the "
     "module's own antenna pad - netless by design per ADR-137 (the antenna "
     "attaches AT the module). Pin order from LoRa128X Rev2.2 s7 via "
     "build_lora1280_footprint.py."),
    ("U5", "RF_GPS:MAX-M10S", "MAX-M10S", "RF_GPS:ublox_MAX", False,
     "ADR-029 D2b: GNSS L1, UART (not I2C) - pins 5 and 13..18 UNASSIGNED."),
    ("U6", "balloon_flight_v10:MS5611_BARO", "MS5611-01BA",
     "Package_LGA:LGA-8_3x5mm_P1.25mm", False,
     "ADR-029: barometer on I2C (GPIO1/2). Symbol = the stock "
     "Sensor_Pressure:MS5611-01BA geometry re-homed into this sheet's own "
     "library, with pin 6 (SDO) retyped passive exactly as v9 did for the "
     "same reason."),
    ("U7", "balloon_flight_v10:TPS7A0233", "TPS7A02",
     "Package_TO_SOT_SMD:SOT-23-5", False,
     "ADR-006: TPS7A02 3.3 V LDO. Pin 4 is NC ON THE PART (TI SBVS277C "
     "Table 5-1) - registered UNASSIGNED, not tied off."),
    ("U_HUB_CVT", "balloon_flight_v10:HUB_CONVERTER",
     "HUB_PV input (part TODO(unverified))",
     "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm", False,
     "ADR-051 s2.1 decision 1: the hub array feeds its OWN converter input "
     "on its OWN nets and is never in series with the wing chain. Pins 1/2/3 "
     "only; the remaining 14 lands are UNASSIGNED."),
    ("C_CAP1", "Device:C_Polarized", "3.3F 2.7V (AVX SCC)",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", False,
     "ADR-006/ADR-047: supercap cell A, positive at VSCAP."),
    ("C_CAP2", "Device:C_Polarized", "3.3F 2.7V (AVX SCC)",
     "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", False,
     "ADR-006/ADR-047: supercap cell B, from SCAP_MID to GND."),
    # --- ADR-121: the programming / USB header ----------------------------
    ("J_PROG", "Connector_Generic:Conn_01x06",
     "PROG/USB (GND 3V3 EN D- D+ IO0)",
     "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical", False,
     "ADR-121: 1 GND, 2 +3V3, 3 /EN, 4 /USB_DN, 5 /USB_DP, 6 /IO0. This "
     "header is what FINALLY nets U1 pins 3/13/14, which were the last three "
     "pin_not_connected errors on the v9 sheet."),
    # --- ADR-046 / ADR-048: the FOUR wing-mount interfaces ----------------
    ("J_W1", "balloon_flight_v10:WING_SOCKET_4P",
     "WING_SOCKET_4P (hub wing interface 1)", "Tracker_Mechanical:Wing_Tab_4P",
     False, "ADR-046 + ADR-048, west seat, rotation 0 deg (ADR-085)."),
    ("J_W2", "balloon_flight_v10:WING_SOCKET_4P",
     "WING_SOCKET_4P (hub wing interface 2)", "Tracker_Mechanical:Wing_Tab_4P",
     False, "ADR-046 + ADR-048, north seat, rotation 90 deg (ADR-085)."),
    ("J_W3", "balloon_flight_v10:WING_SOCKET_4P",
     "WING_SOCKET_4P (hub wing interface 3)", "Tracker_Mechanical:Wing_Tab_4P",
     False, "ADR-046 + ADR-048, east seat, rotation 180 deg (ADR-085)."),
    ("J_W4", "balloon_flight_v10:WING_SOCKET_4P",
     "WING_SOCKET_4P (hub wing interface 4)", "Tracker_Mechanical:Wing_Tab_4P",
     False, "ADR-046 + ADR-048, south seat, rotation 270 deg (ADR-085); "
            "its SOLAR_N (pad 4) is the stack bottom and ties to GND."),
    # === ADR-129 ===========================================================
    # The 25 refs below were DROPPED when v10 was generated by transforming
    # the v9 netlist AS TEXT: that transform carried one end of seventeen nets
    # and dropped the other, which ERC reported as 17 label_dangling errors.
    # The cause was MISSING PARTS, not a drawing defect -- so the parts are
    # restored here and, as with every other ref on this sheet, their
    # connectivity comes from the registry.  ADR-129 decides them group by
    # group; each entry names the decision (D1..D6) it implements.
    # ---------------------------------------------------------------- D1 ---
    ("J_VCC", "balloon_flight_v10:F33_VCC_SEL", "F33_VCC_SEL (VSCAP | +3V3)",
     "Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm", False,
     "ADR-129 D1 / ADR-029 D8 (operator-RATIFIED 2026-10-05): the mandatory "
     "SELECTABLE F33 pin-1 PA rail, a 3-pad solder jumper. pin 1 = /VSCAP "
     "(raw supercap node, PRE-LDO), pin 2 = COM -> /F33_VCC, pin 3 = +3V3 "
     "(TPS7A02 OUT). The rail has THREE possible sources and NO default, so "
     "without this jumper it has no source at all -- which is precisely why "
     "/F33_VCC was dangling on v10. Symbol and footprint reused from v9."),
    ("D1", "Device:D_Schottky", "BAT54", "Diode_SMD:D_SOD-123", False,
     "ADR-129 D1 / ADR-006: solar series-blocking Schottky. Cathode (pin 1) "
     "to /VSCAP, anode (pin 2) to /W1_SOLAR_P; blocks back-feed into the cells "
     "at night. BAT54 (200 mA / 30 V) is CORRECT here because this diode carries "
     "HARVEST current only -- it is not the post-cut bypass path."),
    ("R_BAL1", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-129 D1 / ADR-006: 2x 10 kOhm supercap balancing resistors, upper "
     "cell (/VSCAP -> /SCAP_MID)."),
    ("R_BAL2", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-129 D1 / ADR-006: balancing resistor, lower cell (/SCAP_MID -> "
     "GND)."),
    ("C10", "Device:C", "10uF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-129 D1: +3V3 bulk at the LDO output (LDO stability + ESP32-S3 TX "
     "bursts)."),
    ("C_BULK", "Device:C", "100uF", "Capacitor_SMD:C_1206_3216Metric", False,
     "ADR-129 D1 / ADR-047 s4: bulk cap AT the F33 module VCC pin, sized to "
     "hold a 1.2 A step within 20 mV for 1.67 us."),
    ("C_HF", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-129 D1 / ADR-047 s4: HF bypass at the F33 module VCC pin."),
    ("R_F1", "Device:R", "100R", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-129 D1 / ADR-029 s2(d): the GNSS rail's dedicated RC filter -- "
     "series element (100 R), with C4 as the bulk."),
    ("C4", "Device:C", "10uF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-129 D1 / ADR-029 s2(d): GNSS-rail bulk cap on the filtered feed."),
    ("R_DIV1", "Device:R", "1M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-129 D1 / ADR-006: supercap-rail ADC divider, upper leg (/VSCAP -> "
     "/SCAP_ADC)."),
    ("R_DIV2", "Device:R", "1M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-129 D1 / ADR-006: ADC divider, lower leg (/SCAP_ADC -> GND). NOTE: "
     "/SCAP_ADC still has NO U1 pin -- see OPEN-17/OPEN-25."),
    ("R_MON1", "Device:R", "4.7M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-129 D1 / ADR-047 s6: F33 rail monitor, upper leg (/F33_VCC -> "
     "/F33_VSENSE). 4.7 M keeps the tap at 0.574 uA / 3.1 uW."),
    ("R_MON2", "Device:R", "4.7M", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-129 D1 / ADR-047 s6: monitor lower leg (/F33_VSENSE -> GND); "
     "ratio 0.5 -> 5.4 V reads 2.70 V at the ADC."),
    ("C_MON", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-129 D1 / ADR-047 s6: ADC sample-and-hold reservoir for the 2.35 "
     "MOhm-Thevenin monitor tap (tau = 23.5 ms)."),
    # ---------------------------------------------------------------- D2 ---
    # Bypass diode for every solar cell.  HUB-SIDE on purpose (ADR-054 s2.2,
    # adversarial F3): a cut jettisons the wing AND every part soldered to
    # it, so a wing-board diode cannot bridge the gap it was fitted for, and
    # a cutter flight would be WORSE than baseline (first cut opens the
    # string, array delivers 0.00 W).  SS24 (2 A / 40 V) in SMA, NOT the
    # 200 mA / 30 V BAT54 of the socket spec: post-cut the surviving wings
    # drive the array's full 1.2 A through this diode CONTINUOUSLY for the rest
    # of the flight, and the reverse rating must clear the ~9.58 V cold
    # open-circuit stack.  SMA, not SOD-323: SOD-323 cannot carry 2 A.
    ("D_BP1", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-129 D2 (operator: 'All solar cells should have bypass diodes'): "
     "bypass across wing interface 1 -- cathode (pin 1) /W1_SOLAR_P, anode "
     "(pin 2) /W1_SOLAR_N. POPULATED. Sited beside J_W1 so it cannot be "
     "carried away by the cut it exists to survive."),
    ("D_BP2", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-129 D2: bypass across wing interface 2 -- cathode /W1_SOLAR_N "
     "(which IS the W2_P hub link), anode /W2_SOLAR_N. POPULATED. Sited "
     "beside J_W2."),
    ("D_BP3", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-129 D2: bypass across wing interface 3 -- cathode /W2_SOLAR_N, "
     "anode /W3_SOLAR_N. POPULATED. Sited beside J_W3."),
    ("D_BP4", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-129 D2: bypass across wing interface 4 -- cathode /W3_SOLAR_N, "
     "anode GND. POPULATED. The only one whose anode sits on GND, because "
     "wing 4's SOLAR_N IS the stack bottom (ADR-046 s2.3). Sited beside J_W4."),
    ("D_HUB1", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-129 D2/D3: bypass across hub-array cell 1 -- cathode (pin 1) "
     "/HUB_PV_P, anode (pin 2) /HUB_PV_MID1. POPULATED, hub-side for the same "
     "reason as D_BP1..4 (a diode on the external panel leaves with the panel)."),
    ("D_HUB2", "Device:D_Schottky", "SS24", "Diode_SMD:D_SMA", False,
     "ADR-129 D2/D3: bypass across hub-array cell 2 -- cathode /HUB_PV_MID1, "
     "anode /HUB_PV_N. POPULATED."),
    # --- D3: hub panel BLOCK -- connector only, no on-hub cell lands.
    # The operator: "include a connector for the hub solar cell, but don't
    # make space for it on the hub. Its an external panel like the wing
    # boards." So v10 lands the connector and the two bypass diodes, and
    # reserves NO board area for the cells themselves.
    ("J_HUB_PV", "Connector_Generic:Conn_01x05",
     "HUB_PV_PANEL_5P (P | MID1 | spare | N | GND)",
     "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical", False,
     "ADR-129 D3 + OPEN-26 (amended): the hub solar cell is an EXTERNAL panel, "
     "so v10 carries the connector for it and no board area for the cells. "
     "5 pins: 1 = /HUB_PV_P, 2 = /HUB_PV_MID1 (the interior node between "
     "D_HUB1 and D_HUB2, taken out for observability), 3 = UNASSIGNED spare "
     "(future-proofs the 3-cell H3 sizing at one extra contact), 4 = "
     "/HUB_PV_N, 5 = GND -- the ONE node the hub string may share with the "
     "wing system (ADR-051 s2.1). Placed on an edge for access. The "
     "connector's mechanical FORM is still OPEN (OPEN-26); the PIN COUNT is "
     "decided."),
    # ---------------------------------------------------------------- D5 ---
    # The four nichrome cut channels.  The operator: "Yes please include the
    # nichrome cutoff."  Each carries the cutter drive AND the continuity
    # sense on its wing's ONE reserved RF_FEED conductor, fed from /VSCAP
    # pre-LDO so a cut works with the converter dead (ADR-047 s2.1).  The
    # DRIVE IS MANDATED TO BE A LATCHED ONE-SHOT (ADR-051 s2.5.1): cutting is
    # irreversible and a level-sensitive driver can re-fire on reset,
    # brown-out, retry or a floating gate, each fire costing ~2.59 J of the
    # bank's 16.63 J at the exact moment the bank matters.  The driver PART,
    # the sense divider and the latch topology are TODO(unverified) --
    # OPEN-31.  Restoring the channel lands the NETS AND PADS now; the part
    # is chosen when OPEN-31 closes, and the pads cost no respin.
    ("U_CUT1", "balloon_flight_v10:CUT_CHANNEL",
     "latched cut driver + cut-sense (part TODO(unverified))",
     "Package_TO_SOT_SMD:SOT-23-6", False,
     "ADR-129 D5 / ADR-051 s2.5 item 5 + s2.6: wing 1 cut channel. pin 1 = "
     "/VSCAP (raw supercap, post-BAT54, PRE-LDO), pin 2 = GND, pin 3 = "
     "/CUT_SENSE_W1 = J_W1 pad 3 (RF_FEED). LATCHED ONE-SHOT mandated; must "
     "be serialised in firmware (4 simultaneous fires = 9.9 A = 2.4x the "
     "IRLML2502 class rating). Part OPEN-31."),
    ("U_CUT2", "balloon_flight_v10:CUT_CHANNEL",
     "latched cut driver + cut-sense (part TODO(unverified))",
     "Package_TO_SOT_SMD:SOT-23-6", False,
     "ADR-129 D5: wing 2 cut channel, pin 3 = /CUT_SENSE_W2 = J_W2 pad 3."),
    ("U_CUT3", "balloon_flight_v10:CUT_CHANNEL",
     "latched cut driver + cut-sense (part TODO(unverified))",
     "Package_TO_SOT_SMD:SOT-23-6", False,
     "ADR-129 D5: wing 3 cut channel, pin 3 = /CUT_SENSE_W3 = J_W3 pad 3."),
    ("U_CUT4", "balloon_flight_v10:CUT_CHANNEL",
     "latched cut driver + cut-sense (part TODO(unverified))",
     "Package_TO_SOT_SMD:SOT-23-6", False,
     "ADR-129 D5: wing 4 cut channel, pin 3 = /CUT_SENSE_W4 = J_W4 pad 3."),
]

# --- sheet layout ---------------------------------------------------------
V10_COLUMNS = [
    ["U5", "U6", "U7"],
    ["U1"],
    ["U2"],
    ["U3"],
    ["U_C"],
    ["U_LORA1280"],
    ["C_CAP1", "C_CAP2"],
    ["J_PROG"],
    ["J_W1", "J_W2", "J_W3", "J_W4"],
    ["U_HUB_CVT"],
    # ADR-129: the restored power-management block, the per-cell bypass
    # diodes, the hub panel connector and the four cut channels.
    ["J_VCC", "D1", "R_BAL1", "R_BAL2", "C10", "C_BULK", "C_HF"],
    ["R_F1", "C4", "R_DIV1", "R_DIV2", "R_MON1", "R_MON2", "C_MON"],
    ["D_BP1", "D_BP2", "D_BP3", "D_BP4"],
    ["D_HUB1", "D_HUB2", "J_HUB_PV"],
    ["U_CUT1", "U_CUT2", "U_CUT3", "U_CUT4"],
]
V10_COL_TITLES = [
    "GNSS / BARO / 3V3 LDO",
    "U1 ESP32-S3-WROOM-1U-N8R8",
    "U2 LoRa2021F33-2G4 (433 MHz TX, site A)",
    "U3 bare LoRa2021 (2.4 GHz RX, site B)",
    "U_C bare LoRa2021 (site C, ADR-119)",
    "U_LORA1280 LoRa1280 (2.4 GHz ranging, site D, ADR-139)",
    "SUPERCAP BANK (2 x 3.3 F in series)",
    "J_PROG programming / USB header (ADR-121)",
    "FOUR WING INTERFACES at 90 deg (ADR-046 / ADR-048 / ADR-085)",
    "INDEPENDENT HUB ARRAY CONVERTER INPUT (ADR-051 s2.1)",
    "ADR-129 D1: POWER MANAGEMENT restored (J_VCC / D1 / balancing / bulk / "
    "GNSS RC / dividers / monitor)",
    "ADR-129 D1: supercap divider + F33 rail monitor",
    "ADR-129 D2: WING bypass diodes - HUB-SIDE, SS24 / SMA (ADR-054 s2.2)",
    "ADR-129 D2/D3: HUB-PANEL bypass diodes + the 5-pin panel connector",
    "ADR-129 D5: NICHROME CUT CHANNELS (VSCAP-fed, latched one-shot, OPEN-31)",
]

# --- explicit TODO(unverified) open questions, never guessed ---------------
V10_TODO = [
    ("ADR-128 DIRECTION OF TRUTH",
     "This sheet is DESIGN INTENT, not a mirror. Connectivity is read from "
     "tracker/hardware/connectivity/v10_pinmap.reg (sha256 recorded in the "
     "sheet header below); hub_board_v10.kicad_pcb is a BUILD PRODUCT of that "
     "registry and is NOT read here. Any disagreement between the registry "
     "and the board is a FINDING about the board, not licence to edit the "
     "schematic to match it."),
    ("OPEN-16 J_PROG pin 6 (/IO0)",
     "J_PROG pin 6 carries /IO0 but NOTHING at the U1 end is connected to "
     "it: no U1 pad is assigned to /IO0 on v10. Cause: the WROOM-1U GPIO0 "
     "pad number is named by no in-repo source (an earlier guess of pad 25 "
     "was WRONG - pad 25 is IO48 and carries /U3_RESET_N - and was reverted "
     "in PR #266). Workaround in force: flashing works over USB-Serial-JTAG "
     "via EN + USB D+-, which needs no GPIO0. Closes when the Espressif pin "
     "table is read off a physical module."),
    ("CLOSED-ADR-139 the E28 PA/LNA enables no longer exist",
     "OPEN-E28-EN asked which GPIOs drive the E28-2G4M27SX's RX_EN (8) and "
     "TX_EN (9). ADR-139 replaced that module with the LoRa1280, which has no "
     "PA, no LNA and therefore no enables: the question is CLOSED by the part "
     "change, not waived. If the E28 is ever reinstated the item reopens."),
    ("U_C SITE-C CONTROL NETS",
     "/U_C_CS_N, /U_C_BUSY, /U_C_RESET_N and /U_C_IRQ are single-ended nets: "
     "they leave U_C and have NO destination on v10, because no U1 GPIO is "
     "assigned to them yet (ADR-119 site C). They are drawn as labelled "
     "stubs so the missing MCU side is legible rather than silently absent. "
     "Same class as OPEN-E28-EN."),
    ("U_HUB_CVT 14 UNASSIGNED LANDS",
     "Only pins 1/2/3 (HUB_PV_P / GND / HUB_PV_N) are netted. The land "
     "pattern is a VQFN-16 + EP placeholder for the harvester the hub array "
     "is supposed to feed; the PART is unresolved (ADR-051 s4 items 3/5/6, "
     "OPEN-26), hence 14 unassigned lands. Drawn, not hidden."),
    ("MECHANICAL FEATURES ARE NOT ON THIS SHEET",
     "The v10 board also carries H1..H4 (ADR-124 tether, NPTH D2.5) and "
     "HW1..HW4 (ADR-125 wing-string holes, NPTH D2.5). They are NPTH "
     "mounting holes with NO electrical net, so they are correctly absent "
     "from the netlist and from this sheet; they live in "
     "build_hub_board_v10.py (TETHER / WING_HOLES) and in the board's "
     "mechanical layer. The netlist parity gate can never see them."),
]


def v10_custom_symbols():
    """The repo-local symbols the v10 sheet needs (written to v10_lib/).

    Two of these are REUSES: the F33 and bare-LoRa2021 (x2: U3 and U_C)
    symbols are rebuilt here from the SAME v9 pin tables (V9_F33_PINS /
    V9_BARE_PINS) and the same _v9_symbol() builder, so they are pin-for-pin
    identical to the v9 sheet's symbols - the v10 design carries these parts
    over unchanged (ADR-119).  E28 and the 17-land hub converter are new.
    """
    return {
        "balloon_flight_v10:F33_2G4": _v9_symbol(
            V10_LIBNAME, "F33_2G4", "LoRa2021F33-2G4",
            "balloon_flight_v9:LoRa2021F33_2G4",
            "NiceRF LoRa2021F33-2G4 (SEMTECH LR2021, 18-pad castellated, "
            "built-in +30 dBm PA / 0.5 ppm TCXO). Pin table reused from v9 "
            "(docs/DUAL-VARIANT-DESIGN.md); part unchanged on v10.",
            "https://www.nicerf.com/pdf/lora2021f33-2g4-2w-high-power-high-"
            "speed-multi-band-lr2021-wireless-communication-module-v1.1.pdf",
            V9_F33_PINS),
        "balloon_flight_v10:LR2021_BARE": _v9_symbol(
            V10_LIBNAME, "LR2021_BARE", "LoRa2021_Castellated",
            "balloon_flight_v9:LoRa2021_Castellated",
            "NiceRF LoRa2021 castellated (SEMTECH LR2021, 18-pad, chip-only "
            "2.4 GHz). Pin table reused from v9 UNCHANGED; instantiated "
            "twice on v10 - U3 (site B) and U_C (site C, ADR-119).",
            "", V9_BARE_PINS),
        "balloon_flight_v10:LoRa1280": _v9_symbol(
            V10_LIBNAME, "LoRa1280", "LoRa1280",
            "NiceRF:LoRa1280",
            "G-NiceRF LoRa1280: SX1280, 12.5 dBm, ranging supported, no PA and "
            "no LNA, 16 x 16 mm, 16 pads. Chosen by ADR-139 over the 27 dBm "
            "E28 because two vendors rate the PA-class modules as NOT "
            "supporting ranging, and the 2.4 GHz legal ceiling (10 dBm EIRP) "
            "makes the PA unusable here anyway. Pin 9 is the antenna pad; the "
            "board carries no RF network for it (ADR-137).",
            "", V10_LORA1280_PINS),
        "balloon_flight_v10:TPS7A0233": _v9_symbol(
            V10_LIBNAME, "TPS7A0233", "TPS7A02",
            "Package_TO_SOT_SMD:SOT-23-5",
            "TI TPS7A02 3.3 V ultra-low-Iq LDO (25 nA), SOT-23-5 - ADR-006 "
            "3.3 V rail. Pin table reused from v9. Pin 4 is NC on the part.",
            "", V9_TPS7A02_PINS),
        # A repo-local wing-socket symbol, deliberately NOT a generic pin
        # header: the hub side is a hand-soldered LAND SET, and the net of
        # each land is fixed per interface by the socket spec (ADR-046 / ADR-048).
        "balloon_flight_v10:WING_SOCKET_4P": _v9_symbol(
            V10_LIBNAME, "WING_SOCKET_4P", "WING_SOCKET_4P (hub wing interface)",
            "Tracker_Mechanical:Wing_Tab_4P",
            "Hub-side wing interface / socket land set: 4 lands per face on "
            "BOTH outer layers = 8 copper lands, 4.0 x 1.2 mm, pitch 1.8 mm, "
            "insertion depth 6.0 mm, 90 deg attach. 1 SOLAR_P / 2 GND / "
            "3 RF_FEED (CUT_SENSE_W<n>) / 4 SOLAR_N. All pins typed passive "
            "on purpose - no driver, so no ERC power/PA/RF assertion.",
            "", [("1", "SOLAR_P", "passive"), ("2", "GND", "passive"),
                 ("3", "RF_FEED", "passive"), ("4", "SOLAR_N", "passive")]),
        # --- ADR-051 s2.1 decision 1: the hub string's OWN converter input.
        # A PROVISION - which part (sub-uA harvester H2/H3 vs the main
        # converter M5/M6) is unresolved (ADR-051 s4 items 3 and 5; ADR-054
        # s1.3).  Drawn as the full 17-land pattern it occupies so the
        # unassigned lands are VISIBLE rather than hidden - the ADR-128 rule.
        "balloon_flight_v10:HUB_CONVERTER": _v9_symbol(
            V10_LIBNAME, "HUB_CONVERTER",
            "HUB_PV input (part TODO(unverified))",
            "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm",
            "The hub array's OWN converter / harvester input provision "
            "(ADR-051 s2.1 decision 1). Pin 1 = HUB_PV_P, pin 2 = GND (the ONE "
            "node this string may share with the wing system), pin 3 = HUB_PV_N; "
            "pins 4..17 are UNUSED LANDS. Part OPEN (OPEN-26).",
            "", V10_HUB_CVT_PINS),
        # --- the barometer, re-homed (same reason as v9, see OPEN-7 / ADR-058):
        # the MS5611 runs in I2C mode, so SDO (pin 6) is not a data output.
        # Stock types it `output`; an `output` on GND - which carries a PWR_FLAG,
        # i.e. a synthetic `power output` - makes ERC report "Pins of type Output
        # and Power output are connected": an artefact of the flag, not a defect.
        # Geometry is copied VERBATIM (no pin moves); only the TYPE changes.
        "balloon_flight_v10:MS5611_BARO": _v9_baro_symbol(),
        # --- ADR-129: the two v9 symbols the restored refs reuse, rebuilt into
        # THIS sheet's own library.  Same pin tables and same pin TYPES as the
        # v9 originals, so the two sheets cannot disagree about a part that
        # ADR-129 carries over unchanged.  Building them here (rather than
        # referencing balloon_flight_v9) keeps every symbol this sheet uses
        # resolvable from one library, which is what makes the standalone
        # .kicad_sym export complete.
        "balloon_flight_v10:F33_VCC_SEL": _v9_symbol(
            V10_LIBNAME, "F33_VCC_SEL", "F33_VCC_SEL (VSCAP | +3V3)",
            "Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm",
            "ADR-029 D8 pin-1 rail selector (operator-RATIFIED 2026-10-05), "
            "restored to v10 by ADR-129 D1: a 3-pad solder jumper. pin 2 "
            "COMMON -> /F33_VCC; pin 1 -> /VSCAP (raw supercap node, PRE-LDO) "
            "to fly the F33 2 W PA; pin 3 -> +3V3 (TPS7A02 OUT) to fly the "
            "nested bare LoRa2021. All pins passive: a solder jumper is a "
            "hand-made connection, not a driven port.",
            "", [("1", "A_VSCAP", "passive"), ("2", "COM", "passive"),
                 ("3", "B_3V3", "passive")]),
        "balloon_flight_v10:CUT_CHANNEL": _v9_symbol(
            V10_LIBNAME, "CUT_CHANNEL",
            "latched cut driver + cut-sense (part TODO(unverified))",
            "Package_TO_SOT_SMD:SOT-23-6",
            "Per-wing nichrome cutter channel (ADR-051 s2.5 item 5 + s2.6), "
            "restored to v10 by ADR-129 D5. pin 1 = /VSCAP (raw supercap node, "
            "post-BAT54, PRE-LDO, so a cut works with the converter dead -- "
            "ADR-047 s2.1), pin 2 = GND, pin 3 = the wing's RF_FEED land "
            "(cut DRIVE and continuity SENSE on one conductor plus the shared "
            "ground). THE DRIVE MUST BE A LATCHED ONE-SHOT (ADR-051 s2.5.1). "
            "Exact part, sense divider and latch topology TODO(unverified) -- "
            "OPEN-31.",
            "", [("1", "VSCAP", "passive"), ("2", "GND", "passive"),
                 ("3", "CUT_W", "passive")]),
    }


def _v9_baro_symbol(libname=None):
    """Stock Sensor_Pressure:MS5611-01BA geometry, pin 6 retyped, re-homed."""
    libname = libname or V10_LIBNAME
    dst = libname + ":MS5611_BARO"
    blk = load_lib_symbol("Sensor_Pressure", "MS5611-01BA")
    hits = [m for m in PIN_RE.finditer(blk)
            if m.group(6) == "6" and m.group(1) == "output"]
    if not hits:
        sys.exit("MS5611 SDO pin-type correction: no `output` pin 6 in the "
                 "stock symbol - re-check OPEN-7")
    m = hits[0]
    blk = blk[:m.start(1)] + "passive" + blk[m.end(1):]
    blk = blk.replace('(symbol "Sensor_Pressure:MS5611-01BA"',
                      '(symbol "%s"' % dst, 1)
    blk = blk.replace('"MS5611-01BA_0_1"', '"MS5611_BARO_0_1"')
    blk = blk.replace('"MS5611-01BA_1_1"', '"MS5611_BARO_1_1"')
    assert '(symbol "%s"' % dst in blk, "baro symbol rename failed"
    return blk


def v10_emit():
    sch_path = V10_OUT_SCH
    libdir = V10_LIBDIR
    fplib = V10_FPLIB
    os.makedirs(libdir, exist_ok=True)
    os.makedirs(fplib, exist_ok=True)

    custom = v10_custom_symbols()
    comps = list(V10_COMPONENTS)
    nets = [n for n in V10_NETS if n[1]]

    lib_blocks = dict(custom)
    for (ref, lib_id, value, footprint, dnp, note) in comps:
        if lib_id in lib_blocks:
            continue
        lib, name = lib_id.split(":")
        lib_blocks[lib_id] = load_lib_symbol(lib, name)

    pins_of = {lid: symbol_pins(lib_blocks[lid]) for lid in lib_blocks}
    by_ref = {c[0]: c for c in comps}

    # ---- validation (same two checks v9_emit applies) --------------------
    problems = []
    for (net, nodes, src) in nets:
        for (ref, pin) in nodes:
            if ref not in by_ref:
                problems.append("net %s names unknown ref %s" % (net, ref))
                continue
            if pin not in pins_of[by_ref[ref][1]]:
                problems.append("net %s: %s has no pin %s" % (net, ref, pin))
    # a (ref,pin) may belong to exactly ONE net; a duplicate is a silent short
    owner = {}
    for (net, nodes, src) in nets:
        for nd in nodes:
            if nd in owner and owner[nd] != net:
                problems.append("pin %s.%s is in TWO nets: %s and %s"
                                % (nd[0], nd[1], owner[nd], net))
            owner[nd] = net
    if problems:
        print("V10 VALIDATION FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(3)

    # UNASSIGNED pins: flagged no-connect when the symbol carries the pin, and
    # reported when it does not (a pad the sheet cannot show is a finding).
    nc = []
    undrawn = []
    for (ref, pin, why) in V10_NC:
        if ref not in by_ref:
            undrawn.append((ref, pin, "no such ref on the sheet"))
            continue
        sym_pin = V10_PIN_ALIAS.get((ref, pin), pin)
        if sym_pin in pins_of[by_ref[ref][1]]:
            nc.append((ref, sym_pin, why))
        else:
            undrawn.append((ref, pin, "no symbol pin for this land"))

    # ---- footprints actually placed on the v10 board ---------------------
    fp_sources = [
        (os.path.join(V9_FPLIB, "LoRa2021F33_2G4.kicad_mod"),
         "LoRa2021F33_2G4"),
        (os.path.join(V9_FPLIB, "LoRa2021_Castellated.kicad_mod"),
         "LoRa2021_Castellated"),
        (V10_LORA1280_FP, "LoRa1280"),
    ]
    written = []
    for src, leaf in fp_sources:
        if not os.path.exists(src):
            sys.exit("v10: missing footprint source %s" % src)
        body = open(src).read()
        body = re.sub(r'\(footprint\s+"[^"]*"',
                      '(footprint "%s:%s"\n\t\t(version 20250114)\n'
                      '\t\t(generator "pcbnew")\n\t\t(generator_version "9.0")'
                      % (V10_LIBNAME, leaf), body, count=1)
        with open(os.path.join(fplib, leaf + ".kicad_mod"), "w") as fh:
            fh.write(clean(body) + "\n")
        written.append(leaf)
    with open(V10_FPTABLE, "w") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n'
                 '\t(lib (name "Tracker_Mechanical")(type "KiCad")'
                 '(uri "${KIPRJMOD}/../../footprints/tracker_mechanical.pretty")'
                 '(options "")(descr "Repo-local mechanical footprints: '
                 'Wing_Tab_4P - ADR-046/ADR-048"))\n'
                 '\t(lib (name "%s")(type "KiCad")'
                 '(uri "${KIPRJMOD}/v10_lib/%s.pretty")(options "")'
                 '(descr "v10 flight board footprints"))\n)\n'
                 % (V10_LIBNAME, V10_LIBNAME))

    # ---- placement --------------------------------------------------------
    placed_refs = [r for col in V10_COLUMNS for r in col]
    missing = [c[0] for c in comps if c[0] not in placed_refs]
    if missing:
        sys.exit("v10 layout missing refs: %s" % missing)

    sizes = {c[0]: ((lambda e: (e[2] - e[0], e[3] - e[1]))(
        symbol_extent(lib_blocks[c[1]]))) for c in comps}
    col_x, x = [], 30.48
    for col in V10_COLUMNS:
        col_x.append(x)
        x += max(sizes[r][0] for r in col) + 45.72
    pos, y_bottom = {}, 0.0
    for ci, col in enumerate(V10_COLUMNS):
        y = 50.8
        for ref in col:
            pos[ref] = (round(col_x[ci] / 1.27) * 1.27, round(y / 1.27) * 1.27)
            y += sizes[ref][1] + 25.4
        y_bottom = max(y_bottom, y)

    # ---- sheet text ------------------------------------------------------
    reg_sha = hashlib.sha256(open(V10_REG, "rb").read()).hexdigest()
    body = ['\t(text "BALLOON v10 HUB FLIGHT BOARD - DESIGN-INTENT schematic. '
            'Connectivity is taken from the connectivity registry, NOT from the '
            'PCB. (ADR-128)"\n\t\t(exclude_from_sim no)\n'
            '\t\t(at 30.48 20.32 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
            '(size 2.54 2.54)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
            '\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),
            '\t(text "SOURCE OF TRUTH (pins): '
            'tracker/hardware/connectivity/v10_pinmap.reg   sha256 %s   '
            '(%d net(s), %d UNASSIGNED pin(s)).  hub_board_v10.kicad_pcb is a '
            'BUILD PRODUCT of that registry; the parity gate reads it back to '
            'CHECK, never to author."\n\t\t(exclude_from_sim no)\n'
            '\t\t(at 30.48 24.13 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
            '(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
            '\t\t)\n\t\t(uuid "%s")\n\t)' % (reg_sha[:16], len(nets),
                                             len(V10_NC), uid()),
            '\t(text "PARTS (ADR-118/119/121/123): U1 ESP32-S3-WROOM-1U-N8R8; '
            'U2 LoRa2021F33-2G4 = 433 MHz TX (site A); U3 bare LoRa2021 = '
            '2.4 GHz RX (site B); U_C bare LoRa2021 (site C); U_LORA1280 '
            'NiceRF LoRa1280 = 2.4 GHz ranging, ADR-139 (site D); U5 MAX-M10S '
            'GNSS; U6 MS5611 baro; U7 TPS7A02 LDO; C_CAP1/C_CAP2 supercap '
            'bank; J_PROG prog+USB header; J_W1..J_W4 wing sockets. NO ANT '
            'connectors - ADR-137, antenna at the module."'
            '\n\t\t(exclude_from_sim no)\n'
            '\t\t(at 30.48 26.67 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
            '(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
            '\t\t)\n\t\t(uuid "%s")\n\t)' % uid(),
            ]
    for ci, title in enumerate(V10_COL_TITLES):
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s 43.18 0)\n\t\t(effects\n\t\t\t(font\n\t\t\t\t'
                    '(size 1.524 1.524)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
                    '\t\t)\n\t\t(uuid "%s")\n\t)'
                    % (title.replace('"', "'"),
                       fmt(round(col_x[ci] / 1.27) * 1.27), uid()))

    todo_y = round((y_bottom + 10.16) / 1.27) * 1.27
    for (title, txt) in V10_TODO:
        body.append('\t(text "TODO(unverified) %s -- %s"\n'
                    '\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n'
                    '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n'
                    '\t\t\t)\n\t\t\t(justify left bottom)\n\t\t)\n'
                    '\t\t(uuid "%s")\n\t)'
                    % (title.replace('"', "'"), txt.replace('"', "'"),
                       fmt(30.48), fmt(todo_y), uid()))
        todo_y += 3.81

    net_of, net_src = {}, {}
    for (net, nodes, src) in nets:
        net_src[net] = src
        for nd in nodes:
            net_of[nd] = net
    nc_of = {(r, p): why for (r, p, why) in nc}

    power_syms, wires, labels, ncs = [], [], [], []
    stats = dict(pins=0, nets=set(), labels=0, power=0, nc=0,
                 power_out=set())

    for (ref, lib_id, value, footprint, dnp, note) in comps:
        block = lib_blocks[lib_id]
        sx, sy = pos[ref]
        pins = pins_of[lib_id]
        pin_txt = "".join('\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n'
                          % (n, uid())
                          for n in sorted(pins, key=lambda k: (len(k), k)))
        body.append(
            "\t(symbol\n\t\t(lib_id \"%s\")\n\t\t(at %s %s 0)\n\t\t(unit 1)\n"
            "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
            "\t\t(dnp %s)\n\t\t(uuid \"%s\")\n"
            "\t\t(property \"Reference\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Value\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n\t\t)\n"
            "\t\t(property \"Footprint\" \"%s\"\n\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n"
            "%s\t\t(instances\n\t\t\t(project \"%s\"\n"
            "\t\t\t\t(path \"/%s\"\n\t\t\t\t\t(reference \"%s\")\n"
            "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n"
            % (lib_id, fmt(sx), fmt(sy), "yes" if dnp else "no", uid(),
               ref, fmt(sx + 2.54), fmt(sy - 7.62), value, fmt(sx + 2.54),
               fmt(sy + 2.54), footprint, fmt(sx), fmt(sy), pin_txt,
               V10_PROJECT, inst_path(), ref))

        for pnum in sorted(pins, key=lambda k: (len(k), k)):
            pin = pins[pnum]
            px, py = pin_point(sx, sy, pin)
            stats["pins"] += 1
            key = (ref, pnum)
            if key in net_of:
                net = net_of[key]
                ex, ey = stub_end(sx, sy, pin, 5.08)
                wires.append((px, py, ex, ey))
                if net in POWER_NETS:
                    power_syms.append((net, ex, ey))
                    stats["power"] += 1
                else:
                    # A KiCad LOCAL label must NOT carry a leading "/": `/` is
                    # the hierarchy-path separator, so a label "/SPI1_SCK" is
                    # read as an absolute path, exports as "/{slash}SPI1_SCK"
                    # and does not attach at all (ERC: label_dangling).  The
                    # registry writes nets as "/SPI1_SCK" because that is what
                    # the PCB calls them; KiCad re-adds the leading "/" itself
                    # for a root-sheet local label, which is exactly how the v9
                    # sheet's "SPI1_SCK" label exports as "/SPI1_SCK".
                    labels.append((net.lstrip("/"), ex, ey))
                    stats["labels"] += 1
                stats["nets"].add(net)
                if pin["type"] == "power_out":
                    stats["power_out"].add(net)
            elif key in nc_of:
                ncs.append((px, py))
                stats["nc"] += 1
            # else: deliberately left floating; covered by a V10_TODO note

    # ---- PWR_FLAGs (same placement search v9 uses) ------------------------
    flag_pts = {}
    for (net, x, y) in power_syms:
        flag_pts.setdefault(net, (x, y))
    for (net, x, y) in labels:
        flag_pts.setdefault(net, (x, y))
    pin_type = {}
    for (ref, lib_id, value, footprint, dnp, note) in comps:
        for pn, pin in pins_of[lib_id].items():
            pin_type[(ref, pn)] = pin["type"]
    power_in_nets = {net for (net, nodes, src) in nets
                     if any(pin_type.get(nd) == "power_in" for nd in nodes)}
    flag_nets = ({n for (n, _, _) in power_syms} - stats["power_out"])
    flag_nets |= {n for (n, _, _) in labels
                  if n.startswith("V") or n == "SOLAR_IN"}
    flag_nets |= (power_in_nets - stats["power_out"])

    occ = set()
    for (net, x, y) in power_syms:
        occ.add((round(x, 2), round(y, 2)))
    for (txt, x, y) in labels:
        occ.add((round(x, 2), round(y, 2)))
    for (x1, y1, x2, y2) in wires:
        occ.add((round(x1, 2), round(y1, 2)))
        occ.add((round(x2, 2), round(y2, 2)))

    def flag_offset(fx, fy):
        fx, fy = round(fx, 2), round(fy, 2)
        for dx, dy in ((-5.08, 0), (-7.62, 0), (-10.16, 0), (-12.7, 0),
                       (5.08, 0), (7.62, 0), (10.16, 0), (12.7, 0),
                       (0, -5.08), (0, -7.62), (0, -10.16),
                       (0, 5.08), (0, 7.62), (0, 10.16)):
            tx, ty = round(fx + dx, 2), round(fy + dy, 2)
            if (tx, ty) in occ:
                continue
            clash = False
            if dy == 0:
                lo, hi = sorted((fx, tx))
                clash = any(oy == fy and lo < ox < hi for (ox, oy) in occ)
            else:
                lo, hi = sorted((fy, ty))
                clash = any(ox == fx and lo < oy < hi for (ox, oy) in occ)
            if not clash:
                return dx, dy
        return None

    flags = []
    for net in sorted(flag_nets):
        if net not in flag_pts:
            continue
        x, y = flag_pts[net]
        off = flag_offset(x, y)
        if off is None:
            sys.exit("v10: no free PWR_FLAG stub direction for net %s at "
                     "(%s, %s)" % (net, fmt(x), fmt(y)))
        dx, dy = off
        wires.append((x, y, x + dx, y + dy))
        occ.add((round(x + dx, 2), round(y + dy, 2)))
        flags.append((net, x + dx, y + dy))

    for (x1, y1, x2, y2) in wires:
        body.append('\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
                    '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n'
                    '\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x1), fmt(y1), fmt(x2), fmt(y2), uid()))
    for (txt, x, y) in labels:
        body.append('\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n'
                    '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (txt, fmt(x), fmt(y), uid()))

    for i, (net, x, y) in enumerate(power_syms):
        pref = "#PWR0%03d" % (i + 1)
        body.append(('\t(symbol\n\t\t(lib_id "power:%s")\n\t\t(at %s %s 0)\n'
                     '\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                     '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                     '\t\t(property "Reference" "#PWR"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Value" "%s"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                     '\t\t(instances\n\t\t\t(project "%s"\n'
                     '\t\t\t\t(path "/%s"\n\t\t\t\t\t(reference "#PWR")\n'
                     '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                     % (net, fmt(x), fmt(y), uid(), fmt(x + 2.54),
                        fmt(y + 2.54), net, fmt(x + 2.54), fmt(y - 2.54),
                        fmt(x), fmt(y), uid(), V10_PROJECT, inst_path()))
                     .replace('#PWR', pref))
    for i, (net, x, y) in enumerate(flags):
        body.append('\t(symbol\n\t\t(lib_id "power:PWR_FLAG")\n'
                     '\t\t(at %s %s 0)\n\t\t(unit 1)\n'
                     '\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n'
                     '\t\t(on_board yes)\n\t\t(dnp no)\n\t\t(uuid "%s")\n'
                     '\t\t(property "Reference" "#FLG0%d"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Value" "PWR_FLAG"\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(property "Footprint" ""\n\t\t\t(at %s %s 0)\n'
                     '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n'
                     '\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'
                     '\t\t(pin "1"\n\t\t\t(uuid "%s")\n\t\t)\n'
                     '\t\t(instances\n\t\t\t(project "%s"\n'
                     '\t\t\t\t(path "/%s"\n\t\t\t\t\t(reference "#FLG0%d")\n'
                     '\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n'
                     % (fmt(x), fmt(y), uid(), i + 1, fmt(x + 2.54),
                        fmt(y + 2.54), fmt(x + 2.54), fmt(y - 2.54),
                        fmt(x), fmt(y), uid(), V10_PROJECT, inst_path(), i + 1))
    for (x, y) in ncs:
        body.append('\t(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)\n'
                    % (fmt(x), fmt(y), uid()))

    # power symbol definitions used
    for net in sorted({n for (n, _, _) in power_syms}):
        key = "power:" + net
        if key not in lib_blocks:
            lib_blocks[key] = load_lib_symbol("power", net)
    if flags:
        lib_blocks["power:PWR_FLAG"] = load_lib_symbol("power", "PWR_FLAG")

    libdefs = "\n".join(lib_blocks[k] for k in lib_blocks)
    sch = ('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n'
           '\t(generator_version "9.0")\n\t(uuid "%s")\n\t(paper "A2")\n'
           '\t(title_block\n\t\t(title "Balloon v10 Hub Flight Board")\n'
           '\t\t(date "2026-10-22")\n\t\t(rev "v10-design-intent")\n'
           '\t\t(company "Balloon Relay")\n'
           '\t\t(comment 1 "DESIGN-INTENT schematic. Pin-level connectivity '
           'from connectivity/v10_pinmap.reg sha256 %s; NOT derived from the '
           'PCB. Unassigned pins are drawn floating and listed as '
           'TODO(unverified).")\n'
           '\t)\n\t(lib_symbols\n%s\n\t)\n%s'
           '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n)\n'
           % (uid(), reg_sha[:32], libdefs, "".join(body)))
    with open(sch_path, "w") as fh:
        fh.write(clean(sch))

    # standalone symbol library
    with open(V10_SYMLIB, "w") as fh:
        fh.write('(kicad_symbol_lib\n\t(version 20241209)\n'
                 '\t(generator "kicad_symbol_editor")\n'
                 '\t(generator_version "9.0")\n')
        for k, blk in lib_blocks.items():
            if k.startswith(V10_LIBNAME + ":"):
                fh.write("\t" + blk.replace('(symbol "%s:' % V10_LIBNAME,
                                            '(symbol "', 1) + "\n")
        fh.write(")\n")

    # project file so kicad-cli resolves the shared library tables
    pro_src = os.path.join(HERE, "v_c3_flight.kicad_pro")
    if os.path.exists(pro_src):
        pro = open(pro_src).read().replace("v_c3_flight", V10_PROJECT)
        with open(os.path.join(HERE, V10_PROJECT + ".kicad_pro"), "w") as fh:
            fh.write(pro)

    # Register the v10 symbol/footprint libraries in the SHARED project-local
    # tables.  Without this, ERC reports `The current configuration does not
    # include the symbol library 'balloon_flight_v10'` for every v10 custom
    # part.  Merged, not rewritten: the v_c3 + v9 sheets read the same tables.
    sym_libs = sorted({k.split(":")[0] for k in lib_blocks})
    _v10_sym_entries = []
    for lib in sym_libs:
        if lib == V10_LIBNAME:
            uri = "${KIPRJMOD}/v10_lib/%s.kicad_sym" % V10_LIBNAME
            descr = "v10 flight board symbols (design-intent, ADR-128)"
        elif lib == V9_LIBNAME:
            uri = "${KIPRJMOD}/v9_lib/%s.kicad_sym" % V9_LIBNAME
            descr = "v9 flight board symbols"
        elif lib == "balloon_flight":
            uri = "${KIPRJMOD}/balloon_flight.kicad_sym"
            descr = ""
        else:
            uri = os.path.join(SYMDIR, lib + ".kicad_sym")
            descr = ""
        _v10_sym_entries.append((lib, uri, descr))
    added_sym = merge_lib_table(OUT_LIBTABLE, "sym_lib_table",
                                    _v10_sym_entries)

    fp_entries = [
        (V10_LIBNAME,
         "${KIPRJMOD}/v10_lib/%s.pretty" % V10_LIBNAME,
         "v10 flight board footprints (E28 built from the sidecar pin map)"),
        (V9_LIBNAME,
         "${KIPRJMOD}/v9_lib/%s.pretty" % V9_LIBNAME,
         "v9 flight board footprints"),
        ("balloon_flight", "${KIPRJMOD}/balloon_flight.pretty",
         "Flight board footprints exported from the frozen PCB"),
        ("Tracker_Mechanical",
         "${KIPRJMOD}/../../footprints/tracker_mechanical.pretty",
         "Repo-local mechanical footprints: Wing_Tab_4P - ADR-046/ADR-048"),
    ]
    added_fp = merge_lib_table(OUT_FPTABLE, "fp_lib_table", fp_entries)

    stats["added_lib"] = added_sym
    stats["added_fplib"] = added_fp
    stats["comp"] = len(comps)
    stats["fp"] = written
    stats["undrawn"] = undrawn
    stats["netless"] = len(V10_NC)
    return stats


def main_v10():
    print("v10 schematic variant (design-intent, from the CONNECTIVITY REGISTRY)")
    print("registry     :", V10_REG)
    print("registry sha :", hashlib.sha256(open(V10_REG, "rb").read())
          .hexdigest())
    print("board        : NOT read -- hub_board_v10.kicad_pcb is a build "
          "PRODUCT of the registry (ADR-128)")
    stats = v10_emit()
    print("components   :", stats["comp"])
    print("symbol pins  :", stats["pins"])
    print("net labels   :", stats["labels"])
    print("power pins   :", stats["power"])
    print("no_connect   :", stats["nc"], "of", stats["netless"],
          "UNASSIGNED registry pin(s)")
    if stats["undrawn"]:
        print("registry pins with NO symbol pin (not drawn):")
        for (r, p, why) in stats["undrawn"]:
            print("   - %s.%s : %s" % (r, p, why))
    print("TODO(unverified) notes:", len(V10_TODO))
    print("distinct nets:", len(stats["nets"]), sorted(stats["nets"]))
    print("footprints   :", stats["fp"])
    print("wrote        :", V10_OUT_SCH)
    print("             ", V10_SYMLIB)
    print("             ", V10_FPLIB)


def main():
    sha = hashlib.sha256(open(PCB, "rb").read()).hexdigest()
    print("PCB           :", PCB)
    print("PCB sha256    :", sha)
    print("frozen sha256 :", FROZEN_SHA256)
    print("sha match     :", sha == FROZEN_SHA256)
    if sha != FROZEN_SHA256:
        sys.exit("FROZEN_PCB_SHA_MISMATCH: %s != %s - the schematic mirrors a "
                 "DIFFERENT board; re-freeze and update FROZEN_SHA256 first"
                 % (sha, FROZEN_SHA256))
    fps = parse_pcb(PCB)
    print("footprints    :", len(fps))
    stats, resolved = emit(fps)
    print("symbols placed:", len(resolved))
    print("PCB pads (num):", stats["pins"])
    print("unnamed pads  :", stats["unnamed"], "(mechanical, cannot be netted)")
    print("no_connect    :", stats["nc"], "of which declared GAP:", stats["gap"])
    print("non-power fins:", stats["labels"])
    print("power pins    :", stats["power"])
    print("pwr_flags     :", stats["flags"])
    print("distinct nets :", len(stats["nets"]), sorted(stats["nets"]))
    print("wrote         :", OUT_SCH, OUT_LIBTABLE)


if __name__ == "__main__":
    _target = sys.argv[1] if len(sys.argv) > 1 else ""
    if _target == "v9":
        main_v9()
    elif _target == "v10":
        main_v10()
    else:
        main()
