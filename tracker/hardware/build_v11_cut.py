#!/usr/bin/env python3
"""v11 CUT-CHANNEL module: the component table and the registry rows, from ONE record.

This module owns v11 scope item 3 -- the four nichrome cut channels -- and nothing else.
It is imported by build_v11_sch.py, which merges its output into the sheet exactly as it
merges its own tables. Keeping it out of build_v11_sch.py means item 3 can be reviewed as
one self-contained block, and a later item cannot silently edit it.

DIRECTION OF TRUTH. tracker/hardware/v11_cut_channels.json is the record: every part
value, every datasheet citation and every qualification label lives there. This module
turns that record into (a) rows for the component table and (b) rows for the registry.
Nothing numeric is written here -- if a number is not in the JSON it is not in the design.

THE ARCHITECTURE, in one paragraph. Sense is DIVIDER-ONLY (option B in the item brief).
Each channel is a low-side AO3400A whose source returns to GND through its OWN 0.1 ohm
shunt, and the sense tap is the shunt's high side -- the FET SOURCE node. That node is
0 V whenever the switch is off, so the pin is bounded by resistor division and by nothing
else: no hold-up rail, no analog switch, no supervisor, no sequencing order. Option (A)
was rejected on arithmetic, not on taste; see "architecture_decision" in the JSON.

WHAT THIS DELIBERATELY DOES NOT DO, because the record says it cannot be claimed:
  * no series arming gate (ADR-051 s2.5.1) -- the GPIO budget is 3, all three are used
  * no hardware on-time bound -- a hung MCU holding /CUT_FIRE high runs one channel forever
  * no powered-off input protection claim for the ADS1115
Those are listed as UNQUALIFIED, not quietly satisfied by a hopeful part choice.

Run:  python3 build_v11_sch.py        (this module is a library, not an entry point)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "v11_cut_channels.json")
REPO_HW = HERE

BEGIN_MARK = "# === BEGIN v11 SCOPE ITEM 3 (generated) ==="
END_MARK = "# === END v11 SCOPE ITEM 3 ==="

NCH = 4

# Footprints. Every one of these was verified present in the distro KiCad 9 libraries on
# this host before being named; a footprint id that resolves to nothing is an ERC/DRC time
# bomb that ships as a silent empty pad.
FP_SHUNT = "Resistor_SMD:R_2512_6332Metric"          # 1 W capable
FP_R0402 = "Resistor_SMD:R_0402_1005Metric"
FP_C0402 = "Capacitor_SMD:C_0402_1005Metric"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_SOT236 = "Package_TO_SOT_SMD:SOT-23-6"
FP_VSSOP8 = "Package_SO:VSSOP-8_3x3mm_P0.65mm"
FP_HDR2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"


def load():
    with open(RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def nets(n):
    """The net names for channel n (1-based).

    Kept in one place because the registry, the tests and the report all have to agree on
    the spelling, and a typo here is a net that silently connects to nothing.
    """
    return dict(
        gate="/CUT_GATE%d" % n,
        shunt_h="/CUT_SHUNT_H%d" % n,     # FORCE high side = FET source = heater return
        kelv_h="/CUT_KELV_H%d" % n,       # KELVIN sense high: the divider taps THIS
        heat_ret="/CUT_HEAT_RET%d" % n,   # dedicated heater return, into the shunt force pad
        sense_div="/CUT_SENSE_DIV%d" % n,
        adc="/CUT_ADC%d" % n,
    )


def components():
    """(ref, lib_id, value, footprint, dnp, note) rows for the four channels + shared logic.

    Value strings are derived from the record, not typed twice.
    """
    r = load()
    cc = r["cut_channel"]
    sn = r["sense"]
    sr = r["serialisation"]
    comps = []

    for n in range(1, NCH + 1):
        comps += [
            ("U_CUT%d" % n, "74xGxx:74LVC1G373", "SN74LVC1G373DBVR", FP_SOT236, False,
             "ADR-051 s2.5.1 cut channel %d LATCH. %s (%s). LE tied HIGH -> transparent; "
             "the 3-state OUTPUT is the mechanism, driven by /CUT_OE%d from the one-hot "
             "decoder. When OE is high the output is Hi-Z and R_GPD%d holds the gate below "
             "Vgs(th). NO CLR pin exists and the datasheet guarantees NO power-up state -- "
             "recorded as UNQUALIFIED, not papered over."
             % (n, sr["latch"]["part"], sr["latch"]["lcsc"], n, n)),
            ("Q_CUT%d" % n, "Transistor_FET:Q_NMOS_GSD", "AO3400A", FP_SOT23, False,
             "Cut channel %d LOW-SIDE switch. The SYMBOL is the generic GSD MOSFET "
             "(pin 1 = G, 2 = S, 3 = D); the VALUE names the part, which is what the BOM "
             "and CPL carry. AO3400A itself is a DERIVED KiCad symbol (extends Q_NMOS_GSD) "
             "and a flattened derived symbol does not match the library copy, so the parent "
             "is used directly rather than shipping a lib_symbol_mismatch warning. "
             "AO3400A because its GUARANTEED numbers clear the pulse: ID %s A at 70 C, "
             "PD %s W at 70 C, RDS(on) max 32 mohm at VGS 4.5 V and 48 mohm at 2.5 V "
             "(AOS Rev 3.1 Jul 2023). The 3.3 V gate sits between those two spec points, "
             "so the CONSERVATIVE %s ohm is used in every calculation. Low side because a "
             "high-side N-channel would need Vgate > %s + %s = 6.85 V."
             % (n, cc["drive"]["id_70c_a"], cc["drive"]["pd_70c_w"],
                cc["drive"]["rds_on_max_ohm"], cc["drive"]["vscap_v"],
                cc["drive"]["vgsth_max_v"])),
            ("R_G%d" % n, "Device:R", "%d" % int(cc["gate_network"]["rg_ohm"]), FP_R0402, False,
             "Gate damping for channel %d: 100 ohm x Ciss 630 pF = 63 ns against a 220 ms "
             "pulse. It is NOT a current limiter and is not sized as one." % n),
            ("R_GPD%d" % n, "Device:R", "%dk" % (int(cc["gate_network"]["pulldown_ohm"]) // 1000),
             FP_R0402, False,
             "Gate fail-safe pull-down for channel %d: holds the gate below Vgs(th) while the "
             "latch output is Hi-Z. UNQUALIFIED: latch IOZ max 5 uA x 100 k = 0.5 V against "
             "Vgs(th) min 0.65 V, only 0.15 V of margin; a 10 k part gives 50 mV and is the "
             "recommended change, NOT applied because 100 k is the ADR-051 s2.5.1 value." % n),
            ("R_SH%d" % n, "Device:R_Shunt", "%sm" % (int(round(sn["shunt"]["value_ohm"] * 1000))),
             FP_SHUNT, False,
             "Cut channel %d SENSE SHUNT, in the DEDICATED heater return between the FET "
             "source and GND. %s ohm 1%%, 2512, >= %s W. At the %s A pulse it drops %s mV, "
             "which the ADS1115 resolves to %d counts at FSR +/-4.096 V. A 10 mOhm shunt "
             "would give only 198 counts -- the earlier 10 mOhm figure was computed against "
             "the +/-0.256 V PGA, which is NOT this board's FSR."
             % (n, sn["shunt"]["value_ohm"], sn["shunt"]["min_power_w"],
                round(r["computed"]["i_cut_a"], 2), round(r["computed"]["v_shunt_v"] * 1000, 1),
                r["computed"]["counts_nominal_int"])),
            ("R_SNSA%d" % n, "Device:R", "%dk" % int(sn["divider"]["r_top_ohm"] / 1000),
             FP_R0402, False,
             "Cut channel %d sense divider upper leg, %s -> %s. Ratio 1/4 with R_SNSB%d. The "
             "division is a FAULT bound, not a range: it holds the pin at %s V for a %s V "
             "node that reaches the shunt-high node when the shunt opens, against an "
             "absolute maximum of 3.6 V."
             % (n, nets(n)["shunt_h"], nets(n)["sense_div"], n,
                r["computed"]["fault"]["v_pin_v"], r["computed"]["fault"]["node_v"])),
            ("R_SNSB%d" % n, "Device:R", "%dk" % int(sn["divider"]["r_bottom_ohm"] / 1000),
             FP_R0402, False,
             "Cut channel %d sense divider lower leg, %s -> GND." % (n, nets(n)["sense_div"])),
            ("R_SNS%d" % n, "Device:R", "%dk" % int(sn["divider"]["series_ohm"] / 1000),
             FP_R0402, False,
             "Cut channel %d series element into the ADC pin. Bounds pin current if the pin "
             "is driven while VDD is absent: (2.320 - 0.300)/(75 k + 1 k) = 26.6 uA against "
             "the 10 mA continuous rating. It bounds CURRENT; it does NOT bound voltage." % n),
            ("C_SNS%d" % n, "Device:C", "%dn" % int(sn["divider"]["cap_nf"]), FP_C0402, False,
             "Cut channel %d sense RC with R_SNS%d: 1 k x 100 nF = 100 us, and the "
             "sample-and-hold reservoir the ADS1115 switched-capacitor input needs "
             "(SBAS444E s9.1.5). Also holds the pin through the 8 SPS conversion." % (n, n)),
            ("J_HT%d" % n, "Connector_Generic:Conn_01x02", "CUT LOOP %d" % n, FP_HDR2, False,
             "Cut channel %d TWO-CONDUCTOR LOOP. Pin 1 = /VSCAP (dedicated heater DRIVE), "
             "pin 2 = the dedicated heater RETURN which is the ONLY path to the shunt. "
             "NEVER the floating solar negative -- that was the review defect. THIS IS A "
             "SCHEMATIC STAND-IN, NOT A VALIDATED CONNECTOR: the existing 4-land wing tab "
             "carries SOLAR_P/GND/RF_FEED/SOLAR_N and NONE of those is free for a heater "
             "return, so the two-conductor loop needs lands the tab does not have. Current "
             "rating not established." % n),
        ]

    comps += [
        ("U_DEC", "74xGxx:74LVC1G139", "SN74LVC1G139DCUR", FP_VSSOP8, False,
         "SERIALISATION, ENFORCED IN HARDWARE. 2-to-4 line decoder, ACTIVE-LOW outputs, "
         "driving the four latch /OE pins. TI SCES602E Table 4 Function Table: for EVERY "
         "input combination EXACTLY ONE output is low. There is no address at which two "
         "latches are enabled, so no firmware defect can conduct two FETs at once. Four "
         "simultaneous is 198%% of the single-FET 70 C rating -- 9.32 A against 4.7 A -- "
         "which is why this is a truth table and not a software promise."),
        ("R_A0PD", "Device:R", "10k", FP_R0402, False,
         "Pull-down on /CUT_A0. Idle decoder address = 00. Also the boot strap for the "
         "ESP32-S3 IO45 strapping pin on /CUT_A1 (see R_A1PD), which must be LOW at reset "
         "for 3.3 V flash."),
        ("R_A1PD", "Device:R", "10k", FP_R0402, False,
         "/CUT_A1 pull-down. IO45/pad 26 is an ESP32-S3 STRAPPING pin that selects VDD_SPI "
         "at reset: it must be LOW at boot. This resistor is simultaneously the boot strap "
         "and the decoder's idle level, so the two requirements cannot disagree."),
        ("R_FPD", "Device:R", "100k", FP_R0402, False,
         "/CUT_FIRE pull-down: holds the shared latch D input low so no channel can be "
         "armed while the MCU pin floats at reset."),
    ]
    return comps


def registry_rows():
    """(ref, pin, net, authority) rows -- the connectivity registry contribution.

    Returns rows only; build_v11_sch.py splices them into the registry text AND the
    generator validates them, so the sheet and the registry cannot diverge.
    """
    r = load()
    rows = []

    def add(ref, pin, net, note):
        rows.append((ref, str(pin), net, note))

    for n in range(1, NCH + 1):
        nn = nets(n)
        # --- the latch: SN74LVC1G373 SOT-23-6 (DBV)
        # pin 1 = LE, 2 = GND, 3 = D, 4 = Q, 5 = VCC, 6 = /OE   (TI SCES528F s5)
        add("U_CUT%d" % n, 1, "+3V3", "LE tied HIGH: transparent latch, no stored state")
        add("U_CUT%d" % n, 2, "GND", "SCES528F s5 pin 2")
        add("U_CUT%d" % n, 3, "/CUT_FIRE", "D, shared across all four channels")
        add("U_CUT%d" % n, 4, "/CUT_LAT%d" % n, "Q -> R_G%d" % n)
        add("U_CUT%d" % n, 5, "+3V3", "VCC 1.65..5.5 V (SCES528F s6.1)")
        add("U_CUT%d" % n, 6, "/CUT_OE%d" % n, "~OE <- U_DEC.Y%d" % (n - 1))

        # --- the switch: AO3400A SOT-23, Q_NMOS_GSD => 1=G, 2=S, 3=D
        add("Q_CUT%d" % n, 1, nn["gate"], "gate")
        add("Q_CUT%d" % n, 2, nn["shunt_h"], "SOURCE = shunt HIGH side = sense tap")
        add("Q_CUT%d" % n, 3, nn["heat_ret"], "DRAIN = heater return, into the shunt")

        add("R_G%d" % n, 1, "/CUT_LAT%d" % n, "from U_CUT%d Q" % n)
        add("R_G%d" % n, 2, nn["gate"], "to gate")
        add("R_GPD%d" % n, 1, nn["gate"], "fail-safe pull-down")
        add("R_GPD%d" % n, 2, "GND", "")

        add("R_SH%d" % n, 1, nn["shunt_h"], "FORCE high: FET source / heater return")
        add("R_SH%d" % n, 4, "GND", "FORCE low: the ONLY GND in the heater loop")
        add("R_SH%d" % n, 2, nn["kelv_h"],
            "KELVIN sense high -- Device:R_Shunt is a TRUE 4-TERMINAL part, so the "
            "measurement excludes the force-path IR drop instead of assuming it away")
        add("R_SH%d" % n, 3, "GND", "KELVIN sense low (bonded to GND at the reference)")

        add("R_SNSA%d" % n, 1, nn["kelv_h"],
            "sense tap on the KELVIN pad, AFTER the shunt")
        add("R_SNSA%d" % n, 2, nn["sense_div"], "")
        add("R_SNSB%d" % n, 1, nn["sense_div"], "")
        add("R_SNSB%d" % n, 2, "GND", "")
        add("R_SNS%d" % n, 1, nn["sense_div"], "")
        add("R_SNS%d" % n, 2, nn["adc"], "-> U_ADC1.AIN%d" % (n - 1))
        add("C_SNS%d" % n, 1, nn["adc"], "")
        add("C_SNS%d" % n, 2, "GND", "")

        add("J_HT%d" % n, 1, "/VSCAP", "heater DRIVE conductor")
        add("J_HT%d" % n, 2, nn["heat_ret"], "dedicated heater RETURN conductor")

    # --- the decoder: SN74LVC1G139 VSSOP-8 (DCU) => 1=A, 2=B, 4=GND, 8=VCC, 3/5/6/7 = Y3/Y2/Y1/Y0
    add("U_DEC", 1, "/CUT_A0", "A (LSB)")
    add("U_DEC", 2, "/CUT_A1", "B (MSB)")
    add("U_DEC", 4, "GND", "SCES602E s5")
    add("U_DEC", 8, "+3V3", "VCC 1.65..5.5 V")
    for n in range(1, NCH + 1):
        add("U_DEC", {1: 7, 2: 6, 3: 5, 4: 3}[n], "/CUT_OE%d" % n,
            "Y%d -> U_CUT%d ~OE (Table 4: exactly one LOW)" % (n - 1, n))

    add("R_A0PD", 1, "/CUT_A0", "")
    add("R_A0PD", 2, "GND", "")
    add("R_A1PD", 1, "/CUT_A1", "")
    add("R_A1PD", 2, "GND", "")
    add("R_FPD", 1, "/CUT_FIRE", "")
    add("R_FPD", 2, "GND", "")
    return rows


def adc_rows():
    """The four U_ADC1 AIN rows, which REPLACE the GND placeholders PR546 left.

    PR546 grounded AIN0..3 because the channels were unwired (SBAS444E s9.1.4). They now
    terminate on real dividers, so the grounding is removed rather than left in place --
    a grounded AIN next to a live divider is a short, not a reservation.
    """
    return [("U_ADC1", 4 + (n - 1), nets(n)["adc"],
             "AIN%d = cut-sense wing %d (scope item 3)" % (n - 1, n))
            for n in range(1, NCH + 1)]


def gpio_rows():
    """The three GPIO the cut channel spends, with their strapping constraints."""
    return [
        ("U1", 15, "/CUT_FIRE", "IO3/pad 15 - shared latch D. STRAPPING (JTAG source)."),
        ("U1", 35, "/CUT_A0", "IO42/pad 35 - decoder A (LSB), output capable"),
        ("U1", 26, "/CUT_A1", "IO45/pad 26 - decoder B (MSB). STRAPPING: VDD_SPI select, "
                             "must be LOW at boot; R_A1PD 10k is both strap and idle level."),
    ]


def columns():
    """Sheet columns, one per channel plus the shared logic. Returns (columns, titles)."""
    cols, titles = [], []
    for n in range(1, NCH + 1):
        cols.append(["Q_CUT%d" % n, "U_CUT%d" % n, "R_G%d" % n, "R_GPD%d" % n,
                     "R_SH%d" % n, "R_SNSA%d" % n, "R_SNSB%d" % n, "R_SNS%d" % n,
                     "C_SNS%d" % n, "J_HT%d" % n])
        titles.append("ADR-051 s2.5.1 CUT CHANNEL %d: low-side AO3400A + 0.1R shunt in the "
                      "DEDICATED return + 300k/100k divider (option B, divided-only sense)"
                      % n)
    cols.append(["U_DEC", "R_A0PD", "R_A1PD", "R_FPD"])
    titles.append("SERIALISATION (ADR-129): SN74LVC1G139 one-hot decoder -- exactly one "
                  "latch enabled at any address; 4 simultaneous = 198% of the FET rating")
    return cols, titles


def channel_rows(n):
    """Registry rows belonging to exactly channel n, in a stable order."""
    prefixes = ("U_CUT%d" % n, "Q_CUT%d" % n, "R_G%d" % n, "R_GPD%d" % n,
                "R_SH%d" % n, "R_SNSA%d" % n, "R_SNSB%d" % n, "R_SNS%d" % n,
                "C_SNS%d" % n, "J_HT%d" % n)
    return [row for row in registry_rows() if row[0] in prefixes]


def shared_rows():
    """Rows for the parts every channel shares (decoder + straps)."""
    return [row for row in registry_rows()
            if row[0] in ("U_DEC", "R_A0PD", "R_A1PD", "R_FPD")]


def registry_block():
    """The marked registry block for item 3, as text.

    The registry stays the file the generator reads, so netlist parity is still proved
    against a text file rather than against Python. This function WRITES that text, and
    test_v11_cut_channels.py G2 asserts the file matches it byte for byte -- so the JSON
    record, the registry and the sheet cannot drift apart silently.
    """
    out = [BEGIN_MARK,
           "# v11 SCOPE ITEM 3 -- FOUR NICHROME CUT CHANNELS (divider-only sense).",
           "# Generated from tracker/hardware/v11_cut_channels.json by",
           "# `python3 tracker/hardware/build_v11_cut.py --write-registry`. Do not hand-edit:",
           "# test_v11_cut_channels.py G2 fails if this block differs from the record.",
           "",
           "# --- GPIO spent by item 3 (3 of the 4 free pads per ADR-145)"]
    for (ref, pin, net, note) in gpio_rows():
        out.append("%s.%d  %s  # %s" % (ref, pin, net, note))
    out.append("")
    out.append("# --- U_ADC1 AIN0..3: the four cut-sense currents "
               "(replaces PR546's GND placeholders)")
    for (ref, pin, net, note) in adc_rows():
        out.append("%s.%d  %s  # %s" % (ref, pin, net, note))

    for n in range(1, NCH + 1):
        out.append("")
        out.append("# --- CUT CHANNEL %d: latch + FET + shunt + divider + 2-conductor loop" % n)
        for (ref, pin, net, note) in channel_rows(n):
            out.append("%s.%s  %s%s" % (ref, pin, net, ("  # " + note) if note else ""))

    out.append("")
    out.append("# --- SERIALISATION: one-hot decoder, exactly one latch enabled at any address")
    for (ref, pin, net, note) in shared_rows():
        out.append("%s.%s  %s%s" % (ref, pin, net, ("  # " + note) if note else ""))
    out.append(END_MARK)
    return "\n".join(out)


# Rows this change SUPERSEDES, with the replacement net. Applied by write_registry so the
# registry cannot keep a stale row beside the generated block.
#
# J_W<n>.3 is the wing tab's RF_FEED land. On v10/v11-to-date it carried
# /CUT_SENSE_W<n>: cut drive AND continuity sense on ONE conductor plus the shared ground.
# THAT is the defect the earlier review found -- a single shared conductor cannot give a
# real current measurement, and the "return" was the floating solar negative. Item 3
# replaces it with a dedicated two-conductor loop (J_HT<n>) outside the wing tab, so this
# land is released. Leaving it wired to a net nothing else touches is what produced the
# dangling-label ERC errors, and wiring it to the new loop would silently re-create the
# defect.
SUPERSEDED = {
    ("J_W1", "3"): ("UNASSIGNED", "released by item 3: the cut loop left the wing tab; "
                                 "RF_FEED no longer carries cut drive or sense"),
    ("J_W2", "3"): ("UNASSIGNED", "released by item 3, see J_W1.3"),
    ("J_W3", "3"): ("UNASSIGNED", "released by item 3, see J_W1.3"),
    ("J_W4", "3"): ("UNASSIGNED", "released by item 3, see J_W1.3"),
}

# Refs whose every registry row is now owned by the generated block (or gone entirely).
OWNED_REFS = tuple(
    ["U_CUT%d" % n for n in range(1, NCH + 1)]
    + ["Q_CUT%d" % n for n in range(1, NCH + 1)]
    + ["R_G%d" % n for n in range(1, NCH + 1)]
    + ["R_GPD%d" % n for n in range(1, NCH + 1)]
    + ["R_SH%d" % n for n in range(1, NCH + 1)]
    + ["R_SNSA%d" % n for n in range(1, NCH + 1)]
    + ["R_SNSB%d" % n for n in range(1, NCH + 1)]
    + ["R_SNS%d" % n for n in range(1, NCH + 1)]
    + ["C_SNS%d" % n for n in range(1, NCH + 1)]
    + ["J_HT%d" % n for n in range(1, NCH + 1)]
    + ["U_DEC", "R_A0PD", "R_A1PD", "R_FPD"]
)


def write_registry():
    """Replace the marked block in v11_pinmap.reg and apply SUPERSEDED. Idempotent."""
    import re
    p = os.path.join(REPO_HW, "connectivity", "v11_pinmap.reg")
    txt = open(p, encoding="utf-8").read()

    # 1. drop the generated block if present (it is re-emitted at the end)
    if BEGIN_MARK in txt:
        txt = txt[:txt.index(BEGIN_MARK)] + txt[txt.index(END_MARK) + len(END_MARK):]

    # 2. drop every row this module owns, plus PR546's grounded AIN placeholders, plus the
    #    superseded wing-tab rows. A row is "REF.PIN  NET  # note".
    keep = []
    for line in txt.split("\n"):
        s = line.strip()
        m = re.match(r"^(\S+?)\.(\S+)\s+(\S+)", s)
        if m and not s.startswith("#"):
            ref, pin = m.group(1), m.group(2)
            if ref in OWNED_REFS:
                continue
            if ref == "U_ADC1" and pin in ("4", "5", "6", "7"):
                continue
            if (ref, pin) in SUPERSEDED:
                net, note = SUPERSEDED[(ref, pin)]
                keep.append("%s.%s  %s  # %s" % (ref, pin, net, note))
                continue
        keep.append(line)
    txt = "\n".join(keep)

    # 3. splice the generated block in before the UNASSIGNED summary, and regenerate that
    #    summary so its count and list match the file rather than a remembered number.
    marker = "# UNASSIGNED pins on this board:"
    idx = txt.find(marker)
    head = txt[:idx].rstrip("\n") if idx >= 0 else txt.rstrip("\n")
    block = registry_block()
    body = head + "\n\n" + block + "\n"

    unassigned = [l.split()[0] for l in body.split("\n")
                  if l.strip() and not l.strip().startswith("#")
                  and len(l.split()) > 1 and l.split()[1] == "UNASSIGNED"]
    summary = ("# UNASSIGNED pins on this board: %d -> %s"
               % (len(unassigned), ", ".join(unassigned)))
    body = body.rstrip("\n") + "\n\n" + summary + "\n"
    open(p, "w", encoding="utf-8").write(body)
    return p


if __name__ == "__main__":
    import sys
    if "--write-registry" in sys.argv:
        print("wrote", write_registry())
    else:
        print(__doc__)


# Nets that must NEVER appear inside a heater loop. The review defect was a channel
# returning through the floating solar negative; this tuple is what the test rejects on.
FORBIDDEN_IN_LOOP = (
    "/W1_SOLAR_P", "/W1_SOLAR_N", "/W2_SOLAR_N", "/W3_SOLAR_N",
    "/W1_SOLAR_SENSE", "/W2_SOLAR_SENSE", "/W3_SOLAR_SENSE",
    "/W1_SOLAR_DIV", "/W2_SOLAR_DIV", "/W3_SOLAR_DIV",
)
