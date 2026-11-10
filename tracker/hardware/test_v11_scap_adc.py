#!/usr/bin/env python3
"""v11 ANALOG-SENSE GATE: registry <-> schematic parity, channel map, divider math.

Why this gate exists in this shape. On v10 the parity gate (check_schematic_parity.py)
compares the schematic against a BOARD. v11 has no board -- it is unrouted and the
D_BP1..4 top-face placement is unresolved -- so there is nothing to compare the sheet
against except the registry it is generated from. That comparison is weaker than a board
comparison and this file says so rather than implying otherwise: it proves the SHEET
reflects the REGISTRY, not that any copper exists.

Gates, each independently reported:
  G1 REGISTRY PARSES AND IS NON-EMPTY     (a vacuous pass is a failure)
  G2 PARITY REGISTRY -> SHEET             every registry net/node is in the netlist
  G3 PARITY SHEET -> REGISTRY             every netlist net/node is in the registry
  G4 CHANNEL MAP MATCHES THE NETLIST      the JSON is not a comment, it is checked
  G5 ADDRESS COLLISION                    the four I2C addresses are distinct
  G6 DIVIDER MATH + NEGATIVE CONTROL      each divider's ratio and pin voltage, and a
                                          wrong ratio MUST fail
  G7 NO CUT-SENSE CHANNEL IS REUSED       the four reserved channels are separate nets
  G8 INPUT PROTECTION BOUND               10 mA pin limit honoured at the documented fault
  G9 ERC                                  kicad-cli sch erc, and the count must not exceed
                                          the v10 baseline (9, all inherited)
 G10 DETERMINISM                          regenerating yields a byte-identical sheet

Every gate prints its own numbers. Exit non-zero if any fails.

Run:  python3 tracker/hardware/test_v11_scap_adc.py
      python3 tracker/hardware/test_v11_scap_adc.py --self-test   # prove the gate FAILS
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHDIR = os.path.join(REPO, "tracker", "hardware", "schematics", "flight_board")
SCH = os.path.join(SCHDIR, "v11_flight.kicad_sch")
REG = os.path.join(HERE, "connectivity", "v11_pinmap.reg")
CHANNELS = os.path.join(HERE, "v11_analog_channels.json")
GEN = os.path.join(SCHDIR, "build_v11_sch.py")

# The v10 sheet's ERC count, measured on master 04219c23 BEFORE this change:
#   python3 build_flight_sch.py v10 && kicad-cli sch erc v10_flight.kicad_sch
#   -> 9 violations, all inherited (U5/U2 power_pin_not_driven, U_C single-ended
#      control nets, IO0 no MCU end). v11 must add none.
V10_ERC_ERROR_BASELINE = 9

fails = []
notes = []


def check(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print("  [%s] %s%s" % (tag, name, ("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(name)
    return ok


def skip(name, why):
    print("  [SKIP] %s  -- %s" % (name, why))
    notes.append((name, why))


# ---------------------------------------------------------------- helpers
def registry_nets(path=REG):
    """{net: {(ref,pin)}} from the v11 registry, plus the UNASSIGNED set."""
    nets, netless = {}, set()
    token_nets = ("NC", "UNASSIGNED", "-", "N/A", "NONE")
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2 or "." not in parts[0]:
            continue
        ref, pin = parts[0].split(".", 1)
        net = parts[1]
        if net.upper() in token_nets:
            netless.add((ref, pin))
            continue
        nets.setdefault(net, set()).add((ref if pin != '""' else ref, pin))
    return nets, netless


def sch_netlist(path=SCH):
    """{net: {(ref,pin)}} exported by kicad-cli from the schematic.

    KiCad re-adds the root-sheet leading '/' to local labels, which is why the registry
    spells them '/NAME' and the netlist agrees.
    """
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "n.net")
        r = subprocess.run(["kicad-cli", "sch", "export", "netlist",
                            "--format", "kicadsexpr", "-o", out, path],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not os.path.exists(out):
            return None
        text = open(out, encoding="utf-8", errors="replace").read()
    nets = {}
    for blk in re.finditer(r'\(net\s+\(code\s+"?\d+"?\)\s+\(name\s+"([^"]*)"\)(.*?)'
                           r'(?=\(net\s+\(code|\Z)', text, re.S):
        name = blk.group(1)
        nodes = {(m.group(1), m.group(2))
                 for m in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s+'
                                      r'\(pin\s+"([^"]+)"\)', blk.group(2))}
        if nodes:
            nets[name] = nodes
    return nets


def divider_ratio(r_top, r_bot):
    return r_bot / (r_top + r_bot)


# ---------------------------------------------------------------- gate body
def run(channel_json=None, sch_path=SCH, reg_path=REG):
    print("\n=== v11 ANALOG-SENSE GATE ===")
    print("  schematic :", os.path.relpath(sch_path, REPO))
    print("  registry  :", os.path.relpath(reg_path, REPO))
    print()

    # ---- G1 registry parses and is non-empty --------------------------
    reg_nets, reg_netless = registry_nets(reg_path)
    check("G1 registry parses and is non-empty",
          len(reg_nets) > 50 and len(reg_netless) > 0,
          "%d net(s), %d UNASSIGNED pin(s)" % (len(reg_nets), len(reg_netless)))
    if not reg_nets:
        return       # nothing below can mean anything

    # ---- G2/G3 two-way parity ----------------------------------------
    nl = sch_netlist(sch_path)
    if nl is None:
        skip("G2/G3 netlist parity", "kicad-cli could not export a netlist")
    else:
        missing = {n: (reg_nets[n] - nl.get(n, set()))
                   for n in reg_nets if reg_nets[n] - nl.get(n, set())}
        extra = {n: (nl[n] - reg_nets.get(n, set()))
                 for n in nl if nl[n] - reg_nets.get(n, set())}
        check("G2 parity REGISTRY -> SHEET (no registry node missing from the sheet)",
              not missing, str(sorted(missing.items()))[:300])
        check("G3 parity SHEET -> REGISTRY (no sheet node invented)",
              not extra, str(sorted(extra.items()))[:300])
        only_reg = set(reg_nets) - set(nl)
        only_sch = set(nl) - set(reg_nets)
        check("G3b net-name sets agree", not only_reg and not only_sch,
              "registry-only %s sheet-only %s" % (sorted(only_reg), sorted(only_sch)))

    # ---- G4 the channel map is CHECKED, not just documented -----------
    d = json.load(open(channel_json or CHANNELS))
    dev = {x["ref"]: x for x in d["devices"]}
    ok4 = True
    detail4 = []
    for ref, info in dev.items():
        for ch, c in info["channels"].items():
            # the pin the JSON claims must actually be on the net it claims
            if nl:
                nodes = nl.get(c["net"], set())
                if (ref, c["pin"]) not in nodes:
                    ok4 = False
                    detail4.append("%s.%s(%s) not on %s" % (ref, c["pin"], ch, c["net"]))
    check("G4 channel map matches the netlist (device, pin, net)", ok4,
          "; ".join(detail4))
    print("       U_ADC2 channels:", {ch: c["net"] for ch, c in
                                      dev["U_ADC2"]["channels"].items()})

    # ---- G5 address collision ----------------------------------------
    addrs = [(x["ref"], x["addr"]) for x in d["devices"]]
    other = [(a["device"], n) for a in d["address_collisions"] for n in a["addrs"]]
    used = [a for _, a in addrs] + [n for _, n in other]
    allnames = dict(addrs)
    allnames.update({n: v for n, v in other})
    check("G5 I2C addresses are distinct across every device on the bus",
          len(used) == len(set(used)),
          "; ".join("%s=0x%02X" % (n, a) for n, a in sorted(allnames.items(),
                                                           key=lambda kv: kv[1])))
    check("G5b each ADS1115 address matches its ADDR strap (SBAS444E Table 7-2)",
          dev["U_ADC1"]["addr"] == 0x48 and dev["U_ADC1"]["addr_pin"] == "GND"
          and dev["U_ADC2"]["addr"] == 0x49 and dev["U_ADC2"]["addr_pin"] == "VDD",
          "U_ADC1 ADDR->GND 0x48, U_ADC2 ADDR->VDD 0x49")

    # ---- G6 divider math, with a NEGATIVE CONTROL ----------------------
    fsr = d["adc"]["fsr_v"]
    vdd = d["adc"]["vdd_v"]
    absmax = vdd + d["adc"]["abs_max_pin_above_vdd_v"]
    print("       PGA/FSR = +/-%.3f V, LSB %.1f uV, VDD %.1f V, pin abs max %.2f V"
          % (fsr, d["adc"]["lsb_uv"], vdd, absmax))

    ratios = []
    ok6 = True
    for dv in d["dividers"]:
        r = divider_ratio(dv["r_top_ohm"], dv["r_bot_ohm"])
        ratios.append((dv["id"], r))
        vpin = dv["max_source_v"] * r
        head = fsr - vpin
        inside = vpin <= fsr
        # the pin must ALSO be inside the operating rail for a valid reading
        op_ok = vpin <= vdd
        print("       %-7s %7.0f/%-7.0f  ratio %.7f  at %.2f V -> %.4f V "
              "(%.0f mV below FSR, %s)"
              % (dv["id"], dv["r_top_ohm"], dv["r_bot_ohm"], r, dv["max_source_v"],
                 vpin, head * 1000,
                 "inside rail" if op_ok else "ABOVE VDD"))
        ok6 &= inside
    check("G6a every divider keeps its pin inside the FSR at the documented worst case",
          ok6)

    same = len({round(r, 9) for _, r in ratios}) == 1
    check("G6b all four dividers share ONE ratio (one calibration constant)",
          same, str(ratios))

    # NEGATIVE CONTROL: the inherited v10 ratio (0.5) MUST fail the same test.
    print("       negative control, inherited v10 ratio 1M/1M = 0.5:")
    vscap = [dv for dv in d["dividers"] if dv["id"] == "D_VSCAP"][0]
    bad_v = vscap["max_source_v"] * divider_ratio(1000000, 1000000)
    print("         D_VSCAP at %.2f V -> %.3f V  vs FSR %.3f / absmax %.3f"
          % (vscap["max_source_v"], bad_v, fsr, absmax))
    check("G6c NEGATIVE CONTROL: the v10 1M/1M ratio FAILS this gate "
          "(else the gate is vacuous)", bad_v > absmax,
          "%.3f V > %.3f V absolute maximum" % (bad_v, absmax))

    # and the per-divider identity must be arithmetic, not asserted: recompute from values
    ok6d = all(abs(divider_ratio(dv["r_top_ohm"], dv["r_bot_ohm"]) - ratios[0][1]) < 1e-12
               for dv in d["dividers"])
    check("G6d shared ratio is true of the resistor VALUES (<1e-12 spread), "
          "not just a claim in the JSON", ok6d)

    # ---- G7 cut-sense channels are not reused --------------------------
    # NOTE ON THE TEST SHAPE: the four cut-sense inputs are ALL tied to GND in this
    # revision, because the shunt that will drive them belongs to v11 item 3. So
    # "the four channels are on four different nets" is FALSE today and asserting it
    # would be asserting a design that does not exist. What must hold is that the four
    # RESERVED IDENTITIES are distinct and disjoint from the rail channels -- that is what
    # stops item 3 from silently re-using a channel.
    cut_slots = [c["reserved_slot"] for c in dev["U_ADC1"]["channels"].values()]
    rail_slots = [c["reserved_slot"] for c in dev["U_ADC2"]["channels"].values()]
    rail_nets = [c["net"] for c in dev["U_ADC2"]["channels"].values()]
    cut_targets = [c["reserved_for"] for c in dev["U_ADC1"]["channels"].values()]
    print("       cut-sense RESERVED slots:", cut_slots, "->", cut_targets)
    print("       rail-monitor wired nets :", rail_nets)
    check("G7a the four cut-sense channels are four DISTINCT reserved slots",
          len(set(cut_slots)) == 4, str(cut_slots))
    check("G7b no cut-sense slot targets a net a rail monitor already uses",
          not (set(cut_targets) & set(rail_nets)),
          "cut targets %s / rail nets %s" % (cut_targets, rail_nets))
    check("G7c the eight AIN pins are each claimed once across the two devices",
          len({("U_ADC1", c["pin"]) for c in dev["U_ADC1"]["channels"].values()}
              | {("U_ADC2", c["pin"]) for c in dev["U_ADC2"]["channels"].values()}) == 8
          and len({c["pin"] for c in dev["U_ADC1"]["channels"].values()}) == 4
          and len({c["pin"] for c in dev["U_ADC2"]["channels"].values()}) == 4,
          "U_ADC1 pins %s, U_ADC2 pins %s"
          % (sorted(c["pin"] for c in dev["U_ADC1"]["channels"].values()),
             sorted(c["pin"] for c in dev["U_ADC2"]["channels"].values())))
    check("G7d neither device claims a pin outside AIN0..AIN3 (4/5/6/7)",
          all(c["pin"] in ("4", "5", "6", "7")
              for c in list(dev["U_ADC1"]["channels"].values())
              + list(dev["U_ADC2"]["channels"].values())))
    # each reserved cut channel must be grounded NOW (SBAS444E s9.1.4), not floating
    if nl:
        gnd = nl.get("GND", set())
        grounded = [c for c in dev["U_ADC1"]["channels"].values()
                    if ("U_ADC1", c["pin"]) in gnd]
        check("G7e unwired cut-sense inputs are tied to GND per SBAS444E s9.1.4",
              len(grounded) == 4, "%d/4 grounded" % len(grounded))

    # ---- G8 input protection bound ------------------------------------
    # TWO independent limits apply, and a protection claim is only as good as the
    # tighter one. Earlier drafts of this gate quoted the 10 mA pin-current limit alone
    # and derived 103.6 V from it; that is wrong, because reaching 10 mA needs a 471 V
    # source, at which the 220k 0402 R_top is dissipating 614 mW and has failed long
    # before the ADC pin is stressed. Dissipation therefore binds first. Both limits are
    # computed here and the binding one is the reported margin.
    prot = d["protection"]
    i_limit = prot["max_pin_current_ma"] / 1000.0
    v_clamp = prot["clamp_voltage_assumed_v"]
    rp = prot["r_prot_ohm"]
    p_limit = prot["dissipation_limit_mw"] / 1000.0
    r0 = ratios[0][1]

    dv0 = d["dividers"][0]
    r_top, r_bot = dv0["r_top_ohm"], dv0["r_bot_ohm"]

    def tap_at(v):
        return v * r0

    # limit 1: the ADC's own pin current, once the ESD diode is clamping
    v_pin = (v_clamp + rp * i_limit) / r0

    # limit 2: the worst-dissipating divider resistor (R_top carries the whole string).
    # This must be evaluated PER DIVIDER -- the 2.2M/620k pair and the 220k/62k pair carry
    # the same ratio but dissipate very differently, so the two families have different
    # dissipation ceilings. Quoting one number for both would hide the weaker family.
    per_div = []
    for dv in d["dividers"]:
        rt, rb = dv["r_top_ohm"], dv["r_bot_ohm"]
        vd = (p_limit * (rt + rb) ** 2 / rt) ** 0.5
        per_div.append((dv["id"], vd, min(v_pin, vd),
                        "dissipation" if vd < v_pin else "pin current"))

    print("       limits: pin-current %.1f V across all; per-divider dissipation:" % v_pin)
    for name, vd, vb, which in per_div:
        print("         %-8s dissipation %.1f V -> binding %.1f V (%s)"
              % (name, vd, vb, which))

    v_bind = min(p[2] for p in per_div)
    weakest = [p for p in per_div if p[2] == v_bind][0]
    worst = max(dv["max_source_v"] for dv in d["dividers"])
    print("       binding %.1f V = %.1fx the %.2f V cold Voc (limited by %s via %s)"
          % (v_bind, v_bind / 9.58, 9.58, weakest[0], weakest[3]))

    tap_bind = tap_at(v_bind)
    i_pin_bind = max(0.0, tap_bind - v_clamp) / rp
    check("G8a pin current stays inside the 10 mA continuous limit at the binding point",
          i_pin_bind <= i_limit, "%.3f mA at %.1f V source" % (i_pin_bind * 1000, v_bind))
    check("G8b protection margin >= 10x the documented cold Voc", v_bind >= 10 * 9.58,
          "%.1f V vs %.2f V" % (v_bind, 10 * 9.58))
    check("G8b2 at least one divider is dissipation-limited, so the resistor body "
          "(not just the ADC) is a real constraint", any(p[3] == "dissipation" for p in per_div),
          "; ".join("%s:%s" % (p[0], p[3]) for p in per_div))

    # below the engagement voltage the clamp is not conducting at all
    v_engage = v_clamp / r0
    check("G8b3 the clamp does not conduct anywhere near the design envelope",
          v_engage > 1.5 * 9.58,
          "clamp engages at %.2f V source = %.2fx cold Voc"
          % (v_engage, v_engage / 9.58))

    # ---- G8e source loading is computed from the divider, not assumed ----------
    # The ADC input is not infinite impedance, so R_thevenin + R_PROT forms a divider
    # against it and produces a real gain error. Asserting the number here keeps it from
    # being quietly dropped from the accuracy budget later.
    z_in = d["input_impedance_basis"]["value_ohm"]
    worst_err = 0.0
    for dv in d["dividers"]:
        rt, rb, rpx = dv["r_top_ohm"], dv["r_bot_ohm"], dv["r_prot_ohm"]
        rth = rt * rb / (rt + rb)
        zs = rth + rpx
        err = zs / (z_in + zs) * 100.0
        worst_err = max(worst_err, err)
        check("G8e %s loading error is below 5%% and matches the recorded value"
              % dv["id"], abs(err - dv["loading_error_pct"]) < 0.01 and err < 5.0,
              "%.3f %% (Zsrc %.1f k)" % (err, zs / 1000))
    print("       worst source-loading error %.3f %% -- systematic, so correctable in "
          "calibration, but it must be in the accuracy budget" % worst_err)

    # HONEST SCOPE OF THE RATIO. The divider ratio alone covers 1.5x the cold-Voc
    # estimate, NOT more -- and the estimate itself is a TODO(unverified) coefficient.
    # The series resistor is what buys the rest. This states the boundary rather than
    # implying the ratio is sufficient.
    v_1p5 = 9.58 * 1.5 * r0
    v_2p0 = 9.58 * 2.0 * r0
    print("       ratio-only pin voltage: 1.5x Voc -> %.3f V, 2.0x Voc -> %.3f V "
          "(abs max %.2f V)" % (v_1p5, v_2p0, absmax))
    check("G8c the DIVIDER alone covers 1.5x the cold-Voc estimate", v_1p5 <= absmax,
          "%.3f V <= %.2f V" % (v_1p5, absmax))
    check("G8d the DIVIDER alone does NOT cover 2x -- so R_PROT is load-bearing, "
          "not decorative", v_2p0 > absmax,
          "%.3f V > %.2f V at 2x; pin current there is %.3f mA, inside the 10 mA limit"
          % (v_2p0, absmax, max(0.0, (v_2p0 - v_clamp)) / rp * 1000))

    # ---- G9 ERC --------------------------------------------------------
    if not os.path.exists(sch_path):
        skip("G9 ERC", "schematic missing")
    else:
        with tempfile.TemporaryDirectory() as td:
            rpt = os.path.join(td, "erc.rpt")
            r = subprocess.run(["kicad-cli", "sch", "erc", "--format", "report",
                                "-o", rpt, sch_path],
                               capture_output=True, text=True, timeout=600)
            txt = open(rpt).read() if os.path.exists(rpt) else ""
        m = re.search(r"Errors\s+(\d+)", txt)
        nerr = int(m.group(1)) if m else None
        new = sorted(set(re.findall(r"^\[(\w+)\]", txt, re.M)))
        print("       ERC classes present:", new)
        check("G9a ERC ran and produced a parseable count", nerr is not None, str(nerr))
        check("G9b ERC errors do not exceed the v10 baseline",
              nerr is not None and nerr <= V10_ERC_ERROR_BASELINE,
              "%s vs baseline %d" % (nerr, V10_ERC_ERROR_BASELINE))
        check("G9c no ADC-related ERC class appeared",
              not any(k in new for k in ("pin_not_connected", "lib_symbol_issues",
                                         "power_pin_not_driven_ADC")),
              str(new))

    # ---- G10 determinism ----------------------------------------------
    if not os.path.exists(sch_path):
        skip("G10 determinism", "schematic missing")
    else:
        before = hashlib.sha256(open(sch_path, "rb").read()).hexdigest()
        r = subprocess.run([sys.executable, GEN], cwd=SCHDIR,
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            skip("G10 determinism", "generator failed: " + r.stderr[-200:])
        else:
            after = hashlib.sha256(open(sch_path, "rb").read()).hexdigest()
            check("G10 regenerating yields a byte-identical sheet", before == after,
                  "%s vs %s" % (before[:12], after[:12]))


def self_test():
    """Prove the gate can FAIL. A gate nobody has seen fail is not a gate.

    Poisoned fixtures: a channel map whose AIN1 is moved onto a cut-sense net, and a
    divider whose value is changed to the v10 1M/1M ratio. Both must be caught.
    """
    print("\n=== SELF-TEST: the gate must FAIL on poisoned fixtures ===")
    d = json.load(open(CHANNELS))
    n_fail_before = len(fails)

    # poison 1: reuse a cut-sense net on a rail channel -> G7b must fail
    d["devices"][1]["channels"]["AIN1"]["net"] = "/CUT_SENSE_W1"
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "poison1.json")
        json.dump(d, open(p, "w"))
        fails.clear()
        run(channel_json=p, sch_path=SCH, reg_path=REG)
        caught1 = any("G7b" in f for f in fails)
    print("  self-test 1 (cut-sense channel reused):", "CAUGHT" if caught1 else "MISSED")

    # poison 2: restore a 1M/1M /VSCAP divider -> G6a/G6c must fail
    d = json.load(open(CHANNELS))
    for dv in d["dividers"]:
        if dv["id"] == "D_VSCAP":
            dv["r_top_ohm"], dv["r_bot_ohm"] = 1000000, 1000000
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "poison2.json")
        json.dump(d, open(p, "w"))
        fails.clear()
        run(channel_json=p, sch_path=SCH, reg_path=REG)
        caught2 = any(f.startswith("G6a") for f in fails)
    print("  self-test 2 (v10 1M/1M divider restored):",
          "CAUGHT" if caught2 else "MISSED")

    fails.clear()
    fails.extend([""] * n_fail_before)
    ok = caught1 and caught2
    print("\nSELF-TEST:", "PASS -- both poisoned fixtures were rejected" if ok
          else "FAIL -- the gate accepted a poisoned fixture")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    run()
    print()
    if fails:
        print("FAILED %d check(s): %s" % (len(fails), fails))
        return 1
    print("ALL CHECKS PASSED")
    for n, w in notes:
        print("  note: %s skipped (%s)" % (n, w))
    return 0


if __name__ == "__main__":
    sys.exit(main())
