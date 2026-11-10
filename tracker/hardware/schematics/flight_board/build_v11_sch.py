#!/usr/bin/env python3
"""Generate the v11 hub flight-board schematic from the v11 CONNECTIVITY REGISTRY.

DIRECTION OF TRUTH is the same as v10's (ADR-128): the registry is the source, the
sheet is derived, and the board would be a build product. For v11 there is no board
yet, so nothing is read back from copper.

Why this is a separate file and not a flag on build_flight_sch.py: the v10 generator's
v10_emit() hard-codes V10_* paths, V10_COMPONENTS and the "Balloon v10 Hub Flight Board"
title. Threading a fourth target through it would put v11 edits inside the v10 code path,
where a mistake silently changes the v10 sheet of record. This generator IMPORTS the v10
module for its parsers and symbol builders (one implementation of each), and adds only the
v11 differences.

What v11 adds over v10 -- AND NOTHING ELSE:
  * two ADS1115IDGS, four rail monitors wired, four cut-sense channels reserved
  * /VSCAP divider re-valued 1M/1M -> 2.2M/620k, midpoint split from the ADC net
  * three solar-input dividers + protection resistors + RC caps
  * I2C pull-ups (the v10 bus has none)
Everything inherited from v10 is emitted exactly as v10 emits it.

Scope is deliberately NOT widened: D_BP1..4 stay on the same nets (item 1 is layout-only
and is unresolved), U_CUT1..4 stay placeholders (item 3), and no MCP23017 is added
(item 4). See the header of connectivity/v11_pinmap.reg.

Run:  python3 build_v11_sch.py
"""
import hashlib
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# HERE = <repo>/tracker/hardware/schematics/flight_board, so four levels up is the repo root.
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
assert os.path.isdir(os.path.join(REPO, "tracker", "hardware")), REPO


def _load_v10_module():
    """Import build_flight_sch.py by path.

    It is not a package module and its filename is not an identifier, and its __main__
    guard means importing it performs no generation. Reusing it keeps ONE copy of the
    registry parser, the lib_symbol loader and the emit machinery.
    """
    path = os.path.join(HERE, "build_flight_sch.py")
    spec = importlib.util.spec_from_file_location("build_flight_sch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load_v10_module()

V11_OUT_SCH = os.path.join(HERE, "v11_flight.kicad_sch")
V11_LIBDIR = os.path.join(HERE, "v11_lib")
V11_FPLIB = os.path.join(V11_LIBDIR, "balloon_flight_v11.pretty")
V11_SYMLIB = os.path.join(V11_LIBDIR, "balloon_flight_v11.kicad_sym")
V11_FPTABLE = os.path.join(HERE, "v11_fp-lib-table")
V11_SYMTABLE = os.path.join(HERE, "v11_sym-lib-table")
V11_PROJECT = "v11_flight"
V11_LIBNAME = "balloon_flight_v11"
V11_REG = os.path.join(REPO, "tracker", "hardware", "connectivity",
                       "v11_pinmap.reg")
V11_CHANNELS = os.path.join(REPO, "tracker", "hardware",
                            "v11_analog_channels.json")

# ---------------------------------------------------------------------------
# v11 component table.  Built as v10_COMPONENTS with substitutions, so every
# comment/authority the v10 sheet carries is preserved verbatim and reviewed
# differences are the only differences.
# ---------------------------------------------------------------------------

# ref -> (value, note-override) for the inherited parts whose VALUE changes.
VALUE_CHANGES = {
    "R_DIV1": ("2.2M",
               "ADR-129 D1 / ADR-006, VALUE REVISED BY ADR-148: supercap-rail ADC divider, "
               "upper leg (/VSCAP -> /SCAP_DIV). Was 1M on v10; a 1M/1M (0.5) ratio put "
               "4.64 V on the ADS1115 pin at the documented 9.28 V un-clamped fault, "
               "against an absolute maximum of VDD+0.3 = 3.6 V."),
    "R_DIV2": ("620k",
               "ADR-129 D1 / ADR-006, VALUE REVISED BY ADR-148: ADC divider lower leg "
               "(/SCAP_DIV -> GND). Was 1M on v10. Ratio becomes 0.2198582; total 2.82 M "
               "keeps ADR-047 s6's night budget (10.34 uW vs the recorded 14.58 uW)."),
}

V11_ADDED = [
    # --- ADR-148: the two ADCs -------------------------------------------
    ("U_ADC1", "Analog_ADC:ADS1115IDGS", "ADS1115IDGS",
     "Package_SO:VSSOP-10_3x3mm_P0.5mm", True,      # DNP: see note
     "ADR-148: 16-bit 4-channel I2C ADC, I2C 0x48 (ADDR -> GND, SBAS444E Table 7-2). "
     "DNP IN THIS REVISION. Its four channels are RESERVED for the four nichrome "
     "CUT-SENSE currents, which belong to v11 scope item 3 (real cut driver) and are "
     "not wired yet; ADS1115 input power-sequence qualification is BLOCKED "
     "(docs/analysis/OPEN-25-CUTTER-ADC-SEQUENCE.md). SBAS444E s9.1.4: unused analog "
     "inputs are tied to GND, which is what the registry does. The pads exist so item 3 "
     "needs no respin; the channel allocation is pinned in v11_analog_channels.json so "
     "item 3 cannot silently pick a different one."),
    ("U_ADC2", "Analog_ADC:ADS1115IDGS", "ADS1115IDGS",
     "Package_SO:VSSOP-10_3x3mm_P0.5mm", False,
     "ADR-148: the FITted ADC, I2C 0x49 (ADDR -> VDD, SBAS444E Table 7-2). AIN0 = /VSCAP "
     "(closes the v10 /SCAP_ADC orphan that ended at two unconnected pads), AIN1..3 = the "
     "three solar stack taps. All four at ratio 0.2198582 so one calibration constant and "
     "one PGA setting (FSR +/-4.096 V, LSB 125 uV) serve every channel."),
    ("C_ADC1", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-148 / ADS1115 SBAS444E s10.2: VDD decoupling, 'at least a 0.1 uF', placed at the "
     "VDD pin. Required because the device draws conversion current bursts."),
    ("C_ADC2", "Device:C", "100nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-148 / ADS1115 SBAS444E s10.2: VDD decoupling for U_ADC2."),
    # --- I2C pull-ups: MEASURED MISSING ON v10 ---------------------------
    ("R_PU1", "Device:R", "4k7", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148: /I2C_SCL pull-up. MEASURED on hub_board_v10.kicad_pcb: the I2C bus has NO "
     "pull-up resistors at all -- its only pads are U1.38/U1.39 and U6.7/U6.8. ADR-145 "
     "justified the MCP23017 on the grounds that the bus 'already exists and is already "
     "routed'; routed, yes, but with no pull-ups two more devices cannot drive it. Zero "
     "DC draw at idle: both lines sit high with no current path. 4k7 at 3.3 V is ~0.7 mA "
     "sink, well inside the ADS1115's 3 mA VOL test point (SBAS444E s5.5)."),
    ("R_PU2", "Device:R", "4k7", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148: /I2C_SDA pull-up. See R_PU1."),
    # --- /VSCAP divider: protection resistor + RC -------------------------
    ("R_PROT1", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 input protection: series element between the /VSCAP divider midpoint and the "
     "ADS1115 pin. This is what makes the pin survive a fault, and it survives it by "
     "CURRENT, not by ratio: SBAS444E s5.1 allows 10 mA continuous on any non-supply pin "
     "and s9.1.3 recommends exactly this ('current-limiting resistors on the input "
     "lines'). With the input ESD diode clamping at VDD+0.3 = 3.6 V, a 10 k series "
     "resistor holds pin current under 10 mA up to a 103.6 V tap -- 10.8x the documented "
     "9.58 V cold Voc. See docs/fab/V11-ADC-INPUT-PROTECTION.md."),
    ("C_DIV1", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-148: first-order RC with R_PROT1 (tau 100 us, corner 1.59 kHz) and the "
     "sample-and-hold reservoir the ADS1115's switched-capacitor input needs "
     "(SBAS444E s9.1.5)."),
    # --- solar dividers, three channels ----------------------------------
    ("R_SOL1", "Device:R", "220k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 solar divider D_W1 upper leg, /W1_SOLAR_P (the 12-cell stack top) -> "
     "/W1_SOLAR_DIV. 220k/62k = 0.2198582, the SAME ratio as the /VSCAP divider."),
    ("R_SOL2", "Device:R", "62k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 solar divider D_W1 lower leg, /W1_SOLAR_DIV -> GND."),
    ("R_PROT2", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 input protection for AIN1; same 10 mA current-bound argument as R_PROT1."),
    ("C_SOL1", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-148: RC + sample-and-hold reservoir at AIN1."),
    ("R_SOL3", "Device:R", "220k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 solar divider D_W2 upper leg. Taps /W1_SOLAR_N, which IS the W2_P node -- "
     "the four wings are in SERIES, so this is the 9-cell tap, not a separate wing."),
    ("R_SOL4", "Device:R", "62k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 solar divider D_W2 lower leg."),
    ("R_PROT3", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 input protection for AIN2; same 10 mA current-bound argument as R_PROT1."),
    ("C_SOL2", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-148: RC + sample-and-hold reservoir at AIN2."),
    ("R_SOL5", "Device:R", "220k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 solar divider D_W3 upper leg. Taps /W2_SOLAR_N, which IS the W3_P node -- "
     "the 6-cell tap."),
    ("R_SOL6", "Device:R", "62k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 solar divider D_W3 lower leg."),
    ("R_PROT4", "Device:R", "10k", "Resistor_SMD:R_0402_1005Metric", False,
     "ADR-148 input protection for AIN3; same 10 mA current-bound argument as R_PROT1."),
    ("C_SOL3", "Device:C", "10nF", "Capacitor_SMD:C_0402_1005Metric", False,
     "ADR-148: RC + sample-and-hold reservoir at AIN3."),
]

# Two footprints the v10 sheet never needed.  Copied into the v11 library so the
# v11 fp-lib-table stays single-source, exactly as v10 does for its own parts.
V11_FP_SOURCES = [
    ("/usr/share/kicad/footprints/Package_SO.pretty/VSSOP-10_3x3mm_P0.5mm.kicad_mod",
     "VSSOP-10_3x3mm_P0.5mm"),
]

V11_COLUMNS = B.V10_COLUMNS + [
    # ADR-148 analog sense.  R_DIV1/R_DIV2 are NOT repeated here: they already sit in
    # v10's "supercap divider + F33 rail monitor" column, and v11 only re-values them.
    ["U_ADC1", "U_ADC2"],
    ["R_PROT1", "C_DIV1"],
    ["R_SOL1", "R_SOL2", "R_PROT2", "C_SOL1"],
    ["R_SOL3", "R_SOL4", "R_PROT3", "C_SOL2"],
    ["R_SOL5", "R_SOL6", "R_PROT4", "C_SOL3"],
    ["R_PU1", "R_PU2", "C_ADC1", "C_ADC2"],
]
V11_COL_TITLES = B.V10_COL_TITLES + [
    "ADR-148 ANALOG SENSE: 2x ADS1115IDGS - 0x48 cut-sense (DNP), 0x49 rail monitors",
    "ADR-148 input protection + 10nF RC on the /VSCAP tap (R_DIV1/2 re-valued above)",
    "ADR-148 SOLAR DIVIDER D_W1 220k/62k -> /W1_SOLAR_P (12-cell stack top)",
    "ADR-148 SOLAR DIVIDER D_W2 220k/62k -> /W1_SOLAR_N (9-cell tap = W2_P)",
    "ADR-148 SOLAR DIVIDER D_W3 220k/62k -> /W2_SOLAR_N (6-cell tap = W3_P)",
    "ADR-148 I2C PULL-UPS 2x4k7 (v10 bus had NONE) + ADC VDD decoupling",
]

V11_TODO = B.V10_TODO + [
    ("ADR-148 SOLAR OPEN-CIRCUIT VOLTAGE IS AN ESTIMATE, NOT A MEASUREMENT",
     "Every divider here is sized against V_OC,array(-60 C) = 9.58 V, which comes from "
     "wing-electrical s5.1: V_OC,cell(25 C) = 0.62 V and dV_OC/dT = -2.1 mV/(C.cell), "
     "BOTH marked TODO(unverified), with the cell datasheet absent from this repo. The "
     "protection resistor is sized so the 10 mA pin limit still holds at 103.6 V, i.e. "
     "10.8x this estimate, so a wrong coefficient cannot damage the ADC -- but the "
     "CALIBRATION and the reported volts are only as good as the estimate until the cell "
     "is measured. Closes when the cell datasheet or a bench Voc sweep is on file."),
    ("ADR-148 WING 4 VOLTAGE IS NOT DIRECTLY MEASURABLE",
     "The four wings are in series, so only three independent taps exist (/W1_SOLAR_P, "
     "/W1_SOLAR_N, /W2_SOLAR_N) and all three are measured. Wings 1-3 are differences of "
     "adjacent taps. Wing 4 is /W3_SOLAR_N to GND, and there is no eighth channel: "
     "ADR-148 spent all eight (4 cut + VSCAP + 3 solar). Adding a fifth monitor channel "
     "needs a third ADS1115, which is a v12 decision, not a v11 omission."),
    ("ADR-148 U_ADC1 IS DNP AND ITS INPUTS ARE GROUNDED",
     "The cut-sense channels are allocated but not wired, because the sense element is a "
     "10 mOhm series shunt that belongs to v11 item 3 and the ADS1115 input "
     "power-sequence qualification is BLOCKED (OPEN-25-CUTTER-ADC-SEQUENCE.md: a "
     "3.6 V-powered-off TMUX1511 cannot be credited with protecting an unpowered ADC "
     "from a 5.4 V fault, and no hold-up domain is sized). Do NOT populate U_ADC1 and "
     "drive its AIN pins from the cutter node without closing that document first."),
    ("v11 ITEM 1 (D_BP TOP FACE) IS UNRESOLVED AND IS NOT IN THIS SHEET",
     "ADR-146's job is a LAYOUT change: move D_BP1..D_BP4 to F.Cu. It adds no parts and "
     "changes no net, so this schematic is identical either way. It is NOT done: PR #530 "
     "measured that both proposed D_BP2 top-side sites fail native DRC (SMA pads on "
     "1.27 mm-pitch F.Cu pockets). V11 IS NOT FAB READY until that has a legal site."),
]


def v11_components():
    """v10's component list with the value revisions and the ADR-148 additions."""
    comps = []
    for (ref, lib_id, value, fp, dnp, note) in B.V10_COMPONENTS:
        if ref in VALUE_CHANGES:
            value, note = VALUE_CHANGES[ref]
        # the v10 sheet's own custom parts are re-homed into the v11 library (see
        # v11_emit's `custom`), so the lib_id must follow them or the loader goes
        # looking for balloon_flight_v10 in /usr/share/kicad/symbols.
        lib_id = lib_id.replace(B.V10_LIBNAME + ":", V11_LIBNAME + ":")
        comps.append((ref, lib_id, value, fp, dnp, note))
    comps.extend(V11_ADDED)
    return comps


def v11_read_channels():
    import json
    with open(V11_CHANNELS) as fh:
        return json.load(fh)


def v11_emit():
    """Emit v11_flight.kicad_sch from v11_pinmap.reg.

    Deliberately a near-copy of B.v10_emit(): the two differ only in the paths, the
    component list, the column layout, the TODO list and the title block. Sharing the
    body would mean parameterising the v10 function, i.e. editing the v10 code path to
    add a v11 target -- the failure mode this file exists to avoid.
    """
    os.makedirs(V11_LIBDIR, exist_ok=True)
    os.makedirs(V11_FPLIB, exist_ok=True)

    nets_all, netless = B.v10_read_registry(V11_REG)
    nets = [n for n in nets_all if n[1]]
    comps = v11_components()

    # custom symbols: v10's own set (F33/baro/LoRa2021/etc.) re-homed to the v11 lib name,
    # plus every stock symbol the component table names.
    custom = {}
    for key, blk in B.v10_custom_symbols().items():
        newkey = key.replace(B.V10_LIBNAME + ":", V11_LIBNAME + ":")
        body = blk.replace('(symbol "%s:' % B.V10_LIBNAME,
                           '(symbol "%s:' % V11_LIBNAME, 1)
        # the v10 custom parts carry balloon_flight_v9/... footprint ids; keep them,
        # because the v11 fp-lib-table re-declares the v9 library for that reason.
        custom[newkey] = body

    lib_blocks = dict(custom)
    for (ref, lib_id, value, footprint, dnp, note) in comps:
        if lib_id in lib_blocks:
            continue
        lib, name = lib_id.split(":")
        lib_blocks[lib_id] = B.load_lib_symbol(lib, name)

    pins_of = {lid: B.symbol_pins(lib_blocks[lid]) for lid in lib_blocks}
    by_ref = {c[0]: c for c in comps}

    # ---- validation: registry <-> component table ------------------------
    problems = []
    for (net, nodes, src) in nets:
        for (ref, pin) in nodes:
            if ref not in by_ref:
                problems.append("net %s names unknown ref %s" % (net, ref))
                continue
            if pin not in pins_of[by_ref[ref][1]]:
                problems.append("net %s: %s has no pin %s" % (net, ref, pin))
    owner = {}
    for (net, nodes, src) in nets:
        for nd in nodes:
            if nd in owner and owner[nd] != net:
                problems.append("pin %s.%s is in TWO nets: %s and %s"
                                % (nd[0], nd[1], owner[nd], net))
            owner[nd] = net
    if problems:
        print("V11 VALIDATION FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(3)

    # ---- every component must be on the sheet exactly once ---------------
    placed_refs = [r for col in V11_COLUMNS for r in col]
    dup = {r for r in placed_refs if placed_refs.count(r) > 1}
    if dup:
        sys.exit("v11 layout places refs twice: %s" % sorted(dup))
    missing = [c[0] for c in comps if c[0] not in placed_refs]
    if missing:
        sys.exit("v11 layout missing refs: %s" % missing)
    ghost = [r for r in placed_refs if r not in by_ref]
    if ghost:
        sys.exit("v11 layout places refs with no component: %s" % ghost)

    # ---- UNASSIGNED pins -------------------------------------------------
    nc, undrawn = [], []
    for (ref, pin, why) in netless:
        if ref not in by_ref:
            undrawn.append((ref, pin, "no such ref on the sheet"))
            continue
        sym_pin = B.V10_PIN_ALIAS.get((ref, pin), pin)
        if sym_pin in pins_of[by_ref[ref][1]]:
            nc.append((ref, sym_pin, why))
        else:
            undrawn.append((ref, pin, "no symbol pin for this land"))

    # ---- footprints ------------------------------------------------------
    written = []
    for src, leaf in B.v10_emit_fp_sources():
        if not os.path.exists(src):
            sys.exit("v11: missing footprint source %s" % src)
        body = open(src).read()
        import re
        body = re.sub(r'\(footprint\s+"[^"]*"',
                      '(footprint "%s:%s"\n\t\t(version 20250114)\n'
                      '\t\t(generator "pcbnew")\n\t\t(generator_version "9.0")'
                      % (V11_LIBNAME, leaf), body, count=1)
        with open(os.path.join(V11_FPLIB, leaf + ".kicad_mod"), "w") as fh:
            fh.write(B.clean(body) + "\n")
        written.append(leaf)

    with open(V11_FPTABLE, "w") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n'
                 '\t(lib (name "Tracker_Mechanical")(type "KiCad")'
                 '(uri "${KIPRJMOD}/../../footprints/tracker_mechanical.pretty")'
                 '(options "")(descr "Repo-local mechanical footprints: '
                 'Wing_Tab_4P - ADR-046/ADR-048"))\n'
                 '\t(lib (name "balloon_flight_v9")(type "KiCad")'
                 '(uri "${KIPRJMOD}/v9_lib/balloon_flight_v9.pretty")(options "")'
                 '(descr "v9 flight board footprints - reused by the v11 F33/"'
                 'LoRa2021 modules, ADR-119/ADR-139"))\n'
                 '\t(lib (name "%s")(type "KiCad")'
                 '(uri "${KIPRJMOD}/v11_lib/%s.pretty")(options "")'
                 '(descr "v11 flight board footprints"))\n)\n'
                 % (V11_LIBNAME, V11_LIBNAME))

    # ---- placement -------------------------------------------------------
    sizes = {c[0]: ((lambda e: (e[2] - e[0], e[3] - e[1]))(
        B.symbol_extent(lib_blocks[c[1]]))) for c in comps}
    col_x, x = [], 30.48
    for col in V11_COLUMNS:
        col_x.append(x)
        x += max(sizes[r][0] for r in col) + 45.72
    pos, y_bottom = {}, 0.0
    for ci, col in enumerate(V11_COLUMNS):
        y = 50.8
        for ref in col:
            pos[ref] = (round(col_x[ci] / 1.27) * 1.27, round(y / 1.27) * 1.27)
            y += sizes[ref][1] + 25.4
        y_bottom = max(y_bottom, y)

    # ---- sheet text ------------------------------------------------------
    reg_sha = hashlib.sha256(open(V11_REG, "rb").read()).hexdigest()
    body = ['\t(text "BALLOON v11 HUB FLIGHT BOARD - DESIGN-INTENT schematic. NOT FAB '
            'READY: the board is unrouted and the D_BP1..4 top-face placement (ADR-146) '
            'is unresolved. Connectivity is taken from the v11 connectivity registry, NOT '
            'from a PCB - no v11 PCB exists. (ADR-128 method, ADR-148 content)"\n'
            '\t\t(exclude_from_sim no)\n\t\t(at 30.48 20.32 0)\n\t\t(effects\n'
            '\t\t\t(font\n\t\t\t\t(size 2.54 2.54)\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)' % B.uid(),
            '\t(text "SOURCE OF TRUTH (pins): tracker/hardware/connectivity/'
            'v11_pinmap.reg   sha256 %s   (%d net(s), %d UNASSIGNED pin(s)).   '
            'CHANNEL MAP: tracker/hardware/v11_analog_channels.json"\n'
            '\t\t(exclude_from_sim no)\n\t\t(at 30.48 24.13 0)\n\t\t(effects\n'
            '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)'
            % (reg_sha[:16], len(nets), len(netless), B.uid()),
            ]
    for ci, title in enumerate(V11_COL_TITLES):
        body.append('\t(text "%s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s 43.18 0)\n\t\t(effects\n\t\t\t(font\n'
                    '\t\t\t\t(size 1.524 1.524)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)'
                    % (title.replace('"', "'"),
                       B.fmt(round(col_x[ci] / 1.27) * 1.27), B.uid()))

    todo_y = round((y_bottom + 10.16) / 1.27) * 1.27
    for (title, txt) in V11_TODO:
        body.append('\t(text "TODO(unverified) %s -- %s"\n\t\t(exclude_from_sim no)\n'
                    '\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n'
                    '\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)'
                    % (title.replace('"', "'"), txt.replace('"', "'"),
                       B.fmt(30.48), B.fmt(todo_y), B.uid()))
        todo_y += 3.81

    net_of, net_src = {}, {}
    for (net, nodes, src) in nets:
        net_src[net] = src
        for nd in nodes:
            net_of[nd] = net
    nc_of = {(r, p): why for (r, p, why) in nc}

    power_syms, wires, labels, ncs = [], [], [], []
    stats = dict(pins=0, nets=set(), labels=0, power=0, nc=0, power_out=set())

    for (ref, lib_id, value, footprint, dnp, note) in comps:
        block = lib_blocks[lib_id]
        sx, sy = pos[ref]
        pins = pins_of[lib_id]
        pin_txt = "".join('\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)\n'
                          % (n, B.uid())
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
            % (lib_id, B.fmt(sx), B.fmt(sy), "yes" if dnp else "no", B.uid(),
               ref, B.fmt(sx + 2.54), B.fmt(sy - 7.62), value, B.fmt(sx + 2.54),
               B.fmt(sy + 2.54), footprint, B.fmt(sx), B.fmt(sy), pin_txt,
               V11_PROJECT, B.inst_path(), ref))

        for pnum in sorted(pins, key=lambda k: (len(k), k)):
            pin = pins[pnum]
            px, py = B.pin_point(sx, sy, pin)
            stats["pins"] += 1
            key = (ref, pnum)
            if key in net_of:
                net = net_of[key]
                ex, ey = B.stub_end(sx, sy, pin, 5.08)
                wires.append((px, py, ex, ey))
                if net in B.POWER_NETS:
                    power_syms.append((net, ex, ey))
                    stats["power"] += 1
                else:
                    labels.append((net.lstrip("/"), ex, ey))
                    stats["labels"] += 1
                stats["nets"].add(net)
                if pin["type"] == "power_out":
                    stats["power_out"].add(net)
            elif key in nc_of:
                ncs.append((px, py))
                stats["nc"] += 1

    # ---- PWR_FLAGs: same placement search v9/v10 use ---------------------
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
            sys.exit("v11: no free PWR_FLAG stub direction for net %s at (%s, %s)"
                     % (net, B.fmt(x), B.fmt(y)))
        dx, dy = off
        wires.append((x, y, x + dx, y + dy))
        occ.add((round(x + dx, 2), round(y + dy, 2)))
        flags.append((net, x + dx, y + dy))

    for (x1, y1, x2, y2) in wires:
        body.append('\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n'
                    '\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n'
                    '\t\t(uuid "%s")\n\t)\n'
                    % (B.fmt(x1), B.fmt(y1), B.fmt(x2), B.fmt(y2), B.uid()))
    for (txt, x, y) in labels:
        body.append('\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n'
                    '\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
                    '\t\t\t(justify left bottom)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
                    % (txt, B.fmt(x), B.fmt(y), B.uid()))

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
                     % (net, B.fmt(x), B.fmt(y), B.uid(), B.fmt(x + 2.54),
                        B.fmt(y + 2.54), net, B.fmt(x + 2.54), B.fmt(y - 2.54),
                        B.fmt(x), B.fmt(y), B.uid(), V11_PROJECT, B.inst_path()))
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
                    % (B.fmt(x), B.fmt(y), B.uid(), i + 1, B.fmt(x + 2.54),
                       B.fmt(y + 2.54), B.fmt(x + 2.54), B.fmt(y - 2.54),
                       B.fmt(x), B.fmt(y), B.uid(), V11_PROJECT, B.inst_path(), i + 1))
    for (x, y) in ncs:
        body.append('\t(no_connect\n\t\t(at %s %s)\n\t\t(uuid "%s")\n\t)\n'
                    % (B.fmt(x), B.fmt(y), B.uid()))

    for net in sorted({n for (n, _, _) in power_syms}):
        key = "power:" + net
        if key not in lib_blocks:
            lib_blocks[key] = B.load_lib_symbol("power", net)
    if flags:
        lib_blocks["power:PWR_FLAG"] = B.load_lib_symbol("power", "PWR_FLAG")

    libdefs = "\n".join(lib_blocks[k] for k in lib_blocks)
    sch = ('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n'
           '\t(generator_version "9.0")\n\t(uuid "%s")\n\t(paper "A2")\n'
           '\t(title_block\n\t\t(title "Balloon v11 Hub Flight Board")\n'
           '\t\t(date "2026-11-10")\n\t\t(rev "v11-design-intent-NOT-FAB-READY")\n'
           '\t\t(company "Balloon Relay")\n'
           '\t\t(comment 1 "DESIGN-INTENT schematic. NOT FAB READY: unrouted, and '
           'D_BP1..4 top-face placement (ADR-146) unresolved. Pin-level connectivity '
           'from connectivity/v11_pinmap.reg sha256 %s; NOT derived from a PCB - no v11 '
           'PCB exists. Unassigned pins are drawn floating and listed as '
           'TODO(unverified).")\n'
           '\t)\n\t(lib_symbols\n%s\n\t)\n%s'
           '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n)\n'
           % (B.uid(), reg_sha[:32], libdefs, "".join(body)))
    with open(V11_OUT_SCH, "w") as fh:
        fh.write(B.clean(sch))

    with open(V11_SYMLIB, "w") as fh:
        fh.write('(kicad_symbol_lib\n\t(version 20241209)\n'
                 '\t(generator "kicad_symbol_editor")\n'
                 '\t(generator_version "9.0")\n')
        for k, blk in lib_blocks.items():
            if k.startswith(V11_LIBNAME + ":"):
                fh.write("\t" + blk.replace('(symbol "%s:' % V11_LIBNAME,
                                            '(symbol "', 1) + "\n")
        fh.write(")\n")

    pro_src = os.path.join(HERE, "v_c3_flight.kicad_pro")
    if os.path.exists(pro_src):
        pro = open(pro_src).read().replace("v_c3_flight", V11_PROJECT)
        with open(os.path.join(HERE, V11_PROJECT + ".kicad_pro"), "w") as fh:
            fh.write(pro)

    sym_libs = sorted({k.split(":")[0] for k in lib_blocks})
    entries = []
    for lib in sym_libs:
        if lib == V11_LIBNAME:
            uri = "${KIPRJMOD}/v11_lib/%s.kicad_sym" % V11_LIBNAME
            descr = "v11 flight board symbols (design-intent, ADR-128/ADR-148)"
        elif lib == B.V10_LIBNAME:
            uri = "${KIPRJMOD}/v10_lib/%s.kicad_sym" % B.V10_LIBNAME
            descr = "v10 flight board symbols (reused)"
        elif lib == B.V9_LIBNAME:
            uri = "${KIPRJMOD}/v9_lib/%s.kicad_sym" % B.V9_LIBNAME
            descr = "v9 flight board symbols"
        elif lib == "balloon_flight":
            uri = "${KIPRJMOD}/balloon_flight.kicad_sym"
            descr = ""
        else:
            uri = os.path.join(B.SYMDIR, lib + ".kicad_sym")
            descr = ""
        entries.append((lib, uri, descr))
    added_sym = B.merge_lib_table(B.OUT_LIBTABLE, "sym_lib_table", entries)

    fp_entries = [
        (V11_LIBNAME, "${KIPRJMOD}/v11_lib/%s.pretty" % V11_LIBNAME,
         "v11 flight board footprints"),
        (B.V9_LIBNAME, "${KIPRJMOD}/v9_lib/%s.pretty" % B.V9_LIBNAME,
         "v9 flight board footprints"),
        ("Tracker_Mechanical",
         "${KIPRJMOD}/../../footprints/tracker_mechanical.pretty",
         "Repo-local mechanical footprints: Wing_Tab_4P - ADR-046/ADR-048"),
    ]
    added_fp = B.merge_lib_table(B.OUT_FPTABLE, "fp_lib_table", fp_entries)

    stats.update(dict(added_lib=added_sym, added_fplib=added_fp,
                      comp=len(comps), fp=written, undrawn=undrawn,
                      netless=len(netless), todo=len(V11_TODO)))
    return stats


# The two extra footprint sources are wired in through a small shim so v11_emit can call
# one name: v10's three sources plus VSSOP-10.
def _v10_emit_fp_sources():
    return [
        (os.path.join(B.V9_FPLIB, "LoRa2021F33_2G4.kicad_mod"), "LoRa2021F33_2G4"),
        (os.path.join(B.V9_FPLIB, "LoRa2021_Castellated.kicad_mod"), "LoRa2021_Castellated"),
        (B.V10_LORA1280_FP, "LoRa1280"),
    ] + V11_FP_SOURCES


B.v10_emit_fp_sources = _v10_emit_fp_sources


def main():
    print("v11 schematic variant (design-intent, from the v11 CONNECTIVITY REGISTRY)")
    print("registry     :", V11_REG)
    print("registry sha :", hashlib.sha256(open(V11_REG, "rb").read()).hexdigest())
    print("channels     :", V11_CHANNELS)
    print("board        : NONE -- no v11 PCB exists; this sheet is not derived from copper")
    stats = v11_emit()
    print("components   :", stats["comp"])
    print("symbol pins  :", stats["pins"])
    print("net labels   :", stats["labels"])
    print("power pins   :", stats["power"])
    print("no_connect   :", stats["nc"], "of", stats["netless"], "UNASSIGNED registry pin(s)")
    if stats["undrawn"]:
        print("registry pins with NO symbol pin (not drawn):")
        for (r, p, why) in stats["undrawn"]:
            print("   - %s.%s : %s" % (r, p, why))
    print("TODO(unverified) notes:", stats["todo"])
    print("distinct nets:", len(stats["nets"]), sorted(stats["nets"]))
    print("footprints   :", stats["fp"])
    print("wrote        :", V11_OUT_SCH)
    print("             ", V11_SYMLIB)
    print("             ", V11_FPLIB)


if __name__ == "__main__":
    main()
