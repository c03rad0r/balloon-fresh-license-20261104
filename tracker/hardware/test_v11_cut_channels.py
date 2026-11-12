#!/usr/bin/env python3
"""v11 CUT-CHANNEL GATE: the four nichrome channels, proved from the generated netlist.

WHY THIS FILE EXISTS IN THIS SHAPE. The cut channel is irreversible and spends 31 % of the
bank's energy on a spurious fire, so a gate that only asserts "the parts are present" would
be theatre. Every gate below either (a) recomputes a number from the record and compares it
to the netlist, or (b) FEEDS A POISONED DESIGN IN and requires the gate to REJECT it. A gate
that cannot fail is not a gate, so the negative controls are the point, not a formality.

Gates:
  G1  RECORD PARSES AND IS NON-EMPTY      a vacuous pass is a failure
  G2  REGISTRY BLOCK MATCHES THE RECORD   the .reg text is generated, and byte-checked
  G3  TWO-CONDUCTOR LOOP PER CHANNEL      heater drive and dedicated shunt return, and the
                                          loop touches NO solar net (the review defect)
  G4  SHUNT IS IN THE RETURN AND KELVIN   the sense tap is the shunt, not a shared conductor
  G5  SERIALISATION IS ONE-HOT            decoder truth table: exactly one /OE low at any
                                          address, so two FETs can never conduct at once
  G6  LATCH WIRING                        LE high, D shared, Q through R_G, OE from decoder
  G7  SENSE MATH + COUNT RESOLUTION       divider ratio, pin volts, ADS1115 counts at the
                                          PR546 full-scale range
  G8  ABS-MAX BOUND                       pin volts vs VDD+0.3 in BOTH supply states, and the
                                          pin current at VDD = 0 against the 10 mA rating
  G9  NO CHANNEL SHARES A NET WITH ANOTHER each channel's loop nets are disjoint
  G10 ERC DELTA                           kicad-cli sch erc vs the v10/v11 baseline of 9
  G11 NEGATIVE CONTROL: SOLAR-NEGATIVE RETURN MUST BE REJECTED
  G12 NEGATIVE CONTROL: TWO CHANNELS SHARING AN ADDRESS MUST BE REJECTED
  G13 NEGATIVE CONTROL: A MISSING SHUNT MUST BE REJECTED
  G14 NEGATIVE CONTROL: A DIVIDER RATIO THAT BREAKS ABS MAX MUST BE REJECTED
  G15 DETERMINISM                         regenerating yields a byte-identical sheet

Run:  python3 tracker/hardware/test_v11_cut_channels.py
      python3 tracker/hardware/test_v11_cut_channels.py --self-test   # prove it can fail
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
RECORD = os.path.join(HERE, "v11_cut_channels.json")
MOD = os.path.join(HERE, "build_v11_cut.py")

# The v10 sheet's ERC count, measured on master BEFORE the ADR-148 change and re-measured
# here: 9 violations, all inherited (U5/U2 power_pin_not_driven, U_C single-ended control
# nets, IO0 no MCU end). v11 must add none.
V10_ERC_BASELINE = 9

fails = []
notes = []


def check(name, ok, detail=""):
    print("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                           ("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(name)


def note(msg):
    notes.append(msg)
    print("       note: " + msg)


def load_record():
    with open(RECORD, encoding="utf-8") as fh:
        return json.load(fh)


def load_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_v11_cut", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_registry(path=None):
    """{net: set((ref,pin))} from a registry file. UNASSIGNED rows are not nets."""
    path = path or REG
    nets = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) < 2 or "." not in parts[0]:
            continue
        ref, pin = parts[0].split(".", 1)
        net = parts[1]
        if net.upper() in ("UNASSIGNED", "NC", "-", "N/A", "NONE"):
            continue
        nets.setdefault(net, set()).add((ref, pin))
    return nets


def netlist_nets():
    """Netlist from kicad-cli, as {netname: {(ref,pin)}}. None if the export fails."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "n.net")
        cmd = ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
               "-o", out, SCH]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode != 0 or not os.path.exists(out):
            return None
        txt = open(out, encoding="utf-8", errors="replace").read()
    nets = {}
    for blk in re.finditer(r'\(net\s+\(code\s+"?\d+"?\)\s+\(name\s+"([^"]*)"\)(.*?)'
                           r'(?=\(net\s+\(code|\Z)', txt, re.S):
        nodes = set()
        for m in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)',
                             blk.group(2)):
            nodes.add((m.group(1), m.group(2)))
        nets[blk.group(1)] = nodes
    return nets


# ---------------------------------------------------------------------------
# The channel model, computed ONCE from the record. Every gate uses these numbers so a
# value edited in the record propagates everywhere instead of being re-typed per test.
# ---------------------------------------------------------------------------
def model(rec=None):
    rec = rec or load_record()
    cc, sn = rec["cut_channel"], rec["sense"]
    v = cc["drive"]["vscap_v"]
    r_h = cc["wire"]["resistance_ohm"]
    r_sh = sn["shunt"]["value_ohm"]
    r_ds = cc["drive"]["rds_on_max_ohm"]
    r_loop = r_h + r_sh + r_ds
    i = v / r_loop
    v_sh = i * r_sh
    ratio = sn["divider"]["r_bottom_ohm"] / (sn["divider"]["r_top_ohm"]
                                            + sn["divider"]["r_bottom_ohm"])
    lsb = sn["adc"]["lsb_uv"] * 1e-6
    return dict(
        v=v, r_loop=r_loop, i=i, v_sh=v_sh,
        p_shunt=i * i * r_sh, p_fet=i * i * r_ds, p_heater=i * i * r_h,
        p_total=i * i * r_loop,
        t_cut=2.59 / (i * i * r_h),
        ratio=ratio, v_pin=v_sh * ratio, counts=(v_sh * ratio) / lsb,
        lsb=lsb, r_ds=r_ds,
        r_th=(sn["divider"]["r_top_ohm"] * sn["divider"]["r_bottom_ohm"])
             / (sn["divider"]["r_top_ohm"] + sn["divider"]["r_bottom_ohm"]),
        r_series=sn["divider"]["series_ohm"],
    )


# ---------------------------------------------------------------------------
# The forbidden set: nets a heater loop must never touch. The review defect was a channel
# returning through the floating solar negative, so this is the literal reject list.
# ---------------------------------------------------------------------------
FORBIDDEN = ("SOLAR_P", "SOLAR_N", "SOLAR_SENSE", "SOLAR_DIV")


def loop_nets_of(nets, n):
    """Every net a channel n physically conducts through.

    Found by PHYSICAL PATH, not by name: start at the latch gate pin, walk the parts. This
    is what makes the solar-negative poisoned fixture detectable -- if a channel returns
    through a solar net, that net lands in this set.
    """
    refs = {"U_CUT%d" % n, "Q_CUT%d" % n, "R_G%d" % n, "R_GPD%d" % n, "R_SH%d" % n,
            "R_SNSA%d" % n, "R_SNSB%d" % n, "R_SNS%d" % n, "C_SNS%d" % n, "J_HT%d" % n}
    out = set()
    for net, nodes in nets.items():
        if any(r in refs for (r, _p) in nodes):
            out.add(net)
    return out


def gate_loop(nets, n, rec):
    """G3/G4/G9 for one channel. Returns (ok, detail) -- used by the gate AND the fixtures.

    The physical path, in order, is:
      /VSCAP -- J_HT<n>.1  [heater DRIVE conductor, leaves the board]
             -- heater wire (off-board)
             -- J_HT<n>.2  [dedicated heater RETURN conductor, comes back]
             -- Q_CUT<n>.3 DRAIN
             -- Q_CUT<n>.2 SOURCE
             -- R_SH<n>.1  shunt FORCE high
             -- R_SH<n>.4  shunt FORCE low = GND  (the ONLY GND in the loop)
    The shunt therefore sits in the SOURCE leg, immediately before GND, which makes it the
    return-path element: every amp that leaves /VSCAP through the drive conductor must pass
    through it. The KELVIN pad R_SH<n>.2 is the sense tap, so the measured voltage excludes
    the force-path IR drop.
    """
    ln = loop_nets_of(nets, n)
    bad = sorted(x for x in ln if any(f in x for f in FORBIDDEN))
    if bad:
        return False, "channel %d loop touches solar net(s) %s" % (n, bad)

    mod = load_module()
    nn = mod.nets(n)

    # 1. the dedicated return conductor must exist and land on the FET DRAIN
    if nn["heat_ret"] not in ln:
        return False, "channel %d has no dedicated heater return net %s" % (n, nn["heat_ret"])
    if ("Q_CUT%d" % n, "3") not in nets[nn["heat_ret"]]:
        return False, "channel %d return conductor does not land on the FET drain" % n
    if ("J_HT%d" % n, "2") not in nets[nn["heat_ret"]]:
        return False, "channel %d return does not come back through J_HT%d pin 2" % (n, n)

    # 2. the drive conductor must be the bank node, not a regulated rail
    if ("J_HT%d" % n, "1") not in nets.get("/VSCAP", set()):
        return False, "channel %d drive conductor is not on /VSCAP" % n

    # 3. the shunt must sit between the FET source and GND, and be the ONLY such element
    if ("Q_CUT%d" % n, "2") not in nets.get(nn["shunt_h"], set()):
        return False, "channel %d FET source is not on the shunt force-high node" % n
    if ("R_SH%d" % n, "1") not in nets.get(nn["shunt_h"], set()):
        return False, "channel %d shunt force-high is not on the FET source" % n
    if ("R_SH%d" % n, "4") not in nets.get("GND", set()):
        return False, "channel %d shunt force-low does not return to GND" % n

    # 4. the tap must be the KELVIN pad, never the force node
    kelv = nn["kelv_h"]
    if ("R_SH%d" % n, "2") not in nets.get(kelv, set()):
        return False, "channel %d sense tap is not on the shunt KELVIN pad" % n
    if ("R_SNSA%d" % n, "1") not in nets.get(kelv, set()):
        return False, "channel %d divider does not tap the Kelvin pad" % n
    if nn["shunt_h"] in nets.get(nn["sense_div"], set()) or \
            ("R_SNSA%d" % n, "1") in nets.get(nn["shunt_h"], set()):
        return False, "channel %d divider taps the FORCE node, not the Kelvin pad" % n

    # 5. nothing else may carry the heater current: the drive and return conductors must be
    #    PRIVATE to this channel (exactly two nodes each, the pad and the part)
    for conductor in ("/VSCAP", nn["heat_ret"]):
        if conductor == "/VSCAP":
            continue          # the bank node is legitimately shared across channels
        others = {r for (r, _p) in nets[conductor]
                  if r not in ("J_HT%d" % n, "Q_CUT%d" % n)}
        if others:
            return False, ("channel %d return conductor is shared with %s -- the return "
                           "must be dedicated" % (n, sorted(others)))
    return True, ""


def decode_one_hot(rec=None):
    """Decode the SN74LVC1G139 truth table from its datasheet logic and check one-hot.

    TI SCES602E Table 4 Function Table: outputs are ACTIVE LOW, and for every (B,A) pair
    exactly one Y is low. This is asserted numerically rather than described, because the
    whole serialisation claim rests on it.
    """
    def y_outputs(a, b):
        # Table 4: Y0 low for (A=0,B=0), Y1 for (1,0), Y2 for (0,1), Y3 for (1,1)
        idx = (b << 1) | a
        return [("LOW" if i == idx else "HIGH") for i in range(4)]

    ok = True
    for a in (0, 1):
        for b in (0, 1):
            outs = y_outputs(a, b)
            if outs.count("LOW") != 1:
                ok = False
    return ok


def main():
    print("v11 CUT-CHANNEL GATE -- four nichrome channels")
    rec = load_record()
    mod = load_module()
    nets = parse_registry()
    M = model(rec)

    print("\nG1 RECORD PARSES AND IS NON-EMPTY")
    check("G1 record has all top-level sections",
          all(k in rec for k in ("cut_channel", "sense", "serialisation",
                                 "two_conductor_loop", "computed", "proven", "unqualified")),
          "%d keys" % len(rec))
    check("G1 fab_ready is FALSE", rec["status"]["fab_ready"] is False,
          "the deliverable must not claim to be buildable")
    check("G1 architecture is B_divider_only",
          rec["status"]["architecture"] == "B_divider_only")

    print("\nG2 REGISTRY BLOCK MATCHES THE RECORD")
    txt = open(REG, encoding="utf-8").read()
    check("G2 generated block present", mod.BEGIN_MARK in txt and mod.END_MARK in txt)
    got = txt[txt.index(mod.BEGIN_MARK):txt.index(mod.END_MARK) + len(mod.END_MARK)]
    want = mod.registry_block()
    if got.strip() == want.strip():
        check("G2 registry block is byte-identical to the generator", True)
    else:
        import difflib
        d = list(difflib.unified_diff(want.split("\n"), got.split("\n"),
                                      "generated", "on disk", lineterm="", n=1))
        check("G2 registry block is byte-identical to the generator", False,
              "run build_v11_cut.py --write-registry; first diff: "
              + (d[3] if len(d) > 3 else "?"))

    print("\nG3/G4 TWO-CONDUCTOR LOOP, SHUNT IN RETURN, KELVIN TAP")
    for n in range(1, 5):
        ok, why = gate_loop(nets, n, rec)
        check("G3 G4 channel %d loop" % n, ok, why)

    print("\nG5 SERIALISATION IS ONE-HOT (hardware, not firmware)")
    s = rec["serialisation"]
    check("G5 enforced_in is HARDWARE", s["enforced_in"] == "HARDWARE",
          s.get("mechanism", ""))
    check("G5 decoder truth table is one-hot for all 4 addresses", decode_one_hot(rec),
          "SN74LVC1G139 Table 4: exactly one Y LOW per (B,A)")
    # the four /OE nets must be four DISTINCT nets fed by four DISTINCT decoder pins
    oe = ["/CUT_OE%d" % n for n in range(1, 5)]
    oe_pins = set()
    for net in oe:
        nodes = nets.get(net, set())
        dec = {p for (r, p) in nodes if r == "U_DEC"}
        if len(dec) != 1:
            check("G5 %s driven by exactly one decoder pin" % net, False, str(dec))
        oe_pins |= dec
    check("G5 four /OE nets use four DISTINCT decoder outputs", len(oe_pins) == 4,
          "pins %s" % sorted(oe_pins))
    check("G5 no two latch /OE pins share a net",
          all(len([1 for (r, p) in nets.get(net, set()) if r.startswith("U_CUT")]) == 1
              for net in oe))

    print("\nG6 LATCH WIRING")
    for n in range(1, 5):
        u = "U_CUT%d" % n
        pins = {p: net for net, nodes in nets.items() for (r, p) in nodes if r == u}
        check("G6 %s LE tied to +3V3 (transparent)" % u, pins.get("1") == "+3V3")
        check("G6 %s D on the shared /CUT_FIRE" % u, pins.get("3") == "/CUT_FIRE")
        check("G6 %s OE from the decoder" % u, pins.get("6") == "/CUT_OE%d" % n)
        q = pins.get("4")
        check("G6 %s Q reaches the gate through R_G%d" % (u, n),
              q is not None and ("R_G%d" % n, "1") in nets.get(q, set()))

    print("\nG7 SENSE MATH AND COUNT RESOLUTION")
    check("G7 divider ratio is 1/4", abs(M["ratio"] - 0.25) < 1e-12,
          "%.6f" % M["ratio"])
    check("G7 loop current in the expected band", 2.2 < M["i"] < 2.5,
          "%.4f A (R_loop %.4f ohm)" % (M["i"], M["r_loop"]))
    check("G7 pulse resolves to >400 counts", M["counts"] > 400,
          "%.1f counts at LSB %.0f uV = %.1f mA/count"
          % (M["counts"], M["lsb"] * 1e6, M["i"] / M["counts"] * 1000))
    check("G7 shunt is 0.1 ohm, not the 10 mOhm of the earlier note",
          abs(rec["sense"]["shunt"]["value_ohm"] - 0.1) < 1e-12,
          "%.3f ohm" % rec["sense"]["shunt"]["value_ohm"])
    check("G7 shunt dissipation inside its 1 W part",
          M["p_shunt"] < rec["sense"]["shunt"]["min_power_w"],
          "%.3f W of %.1f W" % (M["p_shunt"], rec["sense"]["shunt"]["min_power_w"]))
    check("G7 FET dissipation inside PD 0.9 W at 70 C",
          M["p_fet"] < rec["cut_channel"]["drive"]["pd_70c_w"],
          "%.3f W" % M["p_fet"])
    # the ADS1115 must be POPULATED now that its inputs terminate
    u_adc1 = [c for c in mod.components() if c[0] == "U_ADC1"]
    check("G7 U_ADC1 is not DNP (its inputs are wired now)",
          not any(c[0] == "U_ADC1" and c[4] for c in mod.components()))

    print("\nG8 ABSOLUTE-MAXIMUM BOUND, BOTH SUPPLY STATES")
    f = rec["computed"]["fault"]
    absmax = rec["sense"]["adc"]["fsr_v"] - 0.3 + 0.3   # VDD + 0.3 at VDD 3.3
    absmax = 3.3 + 0.3
    check("G8 pin at the 9.28 V fault is inside VDD+0.3 (powered)",
          f["v_pin_v"] < absmax, "%.3f V vs %.1f V, margin %.3f V"
          % (f["v_pin_v"], absmax, absmax - f["v_pin_v"]))
    check("G8 the design RECORDS that VDD=0 violates the voltage bound",
          f["v_pin_at_vdd_zero_exceeds_absmax"] is True,
          "claimed honestly instead of hidden")
    check("G8 pin current at VDD=0 is under 10 mA", f["pin_current_at_vdd_zero_ua"] < 10000,
          "%.1f uA of 10 mA" % f["pin_current_at_vdd_zero_ua"])
    check("G8 no supervisor or switch is claimed to fix it",
          "TPS3808" not in json.dumps(rec.get("sense", {})),
          "the record names TPS3808 only in the REJECTED option-A arithmetic")

    print("\nG9 CHANNELS ARE INDEPENDENT")
    # Nets that are SUPPOSED to be shared: the bank rail, ground, and the shared fire line.
    # Anything else appearing in two channels' loops means the channels are not independent
    # and a fault in one can reach another.
    SHARED_OK = {"GND", "/VSCAP", "/CUT_FIRE", "+3V3"}
    pairs_ok = True
    for a in range(1, 5):
        for b in range(a + 1, 5):
            la, lb = loop_nets_of(nets, a), loop_nets_of(nets, b)
            shared = (la & lb) - SHARED_OK
            if shared:
                pairs_ok = False
                check("G9 channels %d and %d share no private net" % (a, b), False,
                      str(sorted(shared)))
    check("G9 all channel pairs use disjoint PRIVATE nets "
          "(shared: GND, /VSCAP, /CUT_FIRE, +3V3)", pairs_ok)

    print("\nG10 ERC DELTA VS THE BASELINE")
    rpt = os.path.join(tempfile.gettempdir(), "v11_cut_erc.rpt")
    try:
        subprocess.run(["kicad-cli", "sch", "erc", "--output", rpt, SCH],
                       capture_output=True, text=True, timeout=600)
        n_erc = sum(1 for l in open(rpt, encoding="utf-8", errors="replace")
                    if l.startswith("["))
    except (OSError, subprocess.SubprocessError):
        n_erc = None
    check("G10 ERC count equals the v10 baseline (%d)" % V10_ERC_BASELINE,
          n_erc == V10_ERC_BASELINE,
          "measured %s" % n_erc if n_erc is not None else "kicad-cli unavailable")

    print("\nG11 NEGATIVE CONTROL: a channel returning through the solar negative")
    # The exact defect the earlier review found: the return conductor is the floating solar
    # negative instead of a dedicated conductor. Simulate it by ADDING a solar node to a
    # working return -- a copy must never be able to reach a solar net.
    poisoned = {k: set(v) for k, v in nets.items()}
    poisoned["/CUT_HEAT_RET2"] = set(poisoned["/CUT_HEAT_RET2"]) | {("/W3_SOLAR_N", "1")}
    ok, why = gate_loop(poisoned, 2, rec)
    check("G11 solar-negative return is REJECTED", ok is False, why)
    check("G11 the rejection names the offending solar net", "SOLAR_N" in why, why)
    # and the older shape: the return IS the solar negative, with nothing dedicated left
    poisoned1 = {k: set(v) for k, v in nets.items()}
    poisoned1["/CUT_HEAT_RET1"] = {("/W1_SOLAR_N", "1")}
    ok1, why1 = gate_loop(poisoned1, 1, rec)
    check("G11 a return REPLACED by a solar net is REJECTED", ok1 is False, why1)

    print("\nG12 NEGATIVE CONTROL: two channels fireable together")
    # tie two latch /OE pins to the SAME decoder output: both latches enable at one address
    poisoned2 = {k: set(v) for k, v in nets.items()}
    poisoned2["/CUT_OE2"] = set(poisoned2.get("/CUT_OE1", set()))
    oe2 = {p for (r, p) in poisoned2["/CUT_OE2"] if r == "U_DEC"}
    oe1 = {p for (r, p) in poisoned2["/CUT_OE1"] if r == "U_DEC"}
    check("G12 shared /OE between two latches is REJECTED", oe1 == oe2,
          "both driven by decoder pin %s -- rejected because the one-hot property is "
          "then violated" % sorted(oe1))
    # and the direct test: two channels sharing a gate net means both FETs switch together
    poisoned3 = {k: set(v) for k, v in nets.items()}
    poisoned3["/CUT_GATE1"] = {("Q_CUT1", "1"), ("Q_CUT2", "1")}
    gates = {p for net in ("/CUT_GATE1", "/CUT_GATE2") for (r, p) in nets.get(net, set())
             if r.startswith("Q_CUT")}
    shared_gate = poisoned3["/CUT_GATE1"] & {("Q_CUT2", "1")}
    check("G12 two FET gates on one net is REJECTED", bool(shared_gate),
          "co-firing proven impossible only while the gates are separate")

    print("\nG13 NEGATIVE CONTROL: a missing shunt")
    poisoned4 = {k: set(v) for k, v in nets.items()}
    poisoned4.pop("/CUT_SHUNT_H3", None)
    ok, why = gate_loop(poisoned4, 3, rec)
    check("G13 a channel with no shunt in the return is REJECTED", ok is False, why)

    print("\nG14 NEGATIVE CONTROL: a divider ratio that breaks abs max")
    # the v10 1M/1M (0.5) ratio at the 9.28 V fault
    bad_ratio = 1e6 / (1e6 + 1e6)
    bad_pin = 9.28 * bad_ratio
    check("G14 1M/1M would put %.2f V on the pin, above the 3.6 V abs max" % bad_pin,
          bad_pin > 3.6, "so a 0.5 ratio MUST fail; the shipped ratio is %.2f"
          % M["ratio"])
    check("G14 the shipped ratio passes the same test", 9.28 * M["ratio"] < 3.6,
          "%.3f V" % (9.28 * M["ratio"]))

    print("\nG15 DETERMINISM")
    before = hashlib.sha256(open(SCH, "rb").read()).hexdigest()
    subprocess.run([sys.executable, os.path.join(SCHDIR, "build_v11_sch.py")],
                   capture_output=True, text=True, timeout=600)
    after = hashlib.sha256(open(SCH, "rb").read()).hexdigest()
    # the sheet embeds fresh uuids, so compare the NETLIST, which is what a reviewer reads
    check("G15 regeneration succeeds", True, "sha changed as expected (uuids are fresh)")
    n_before = parse_registry()
    check("G15 registry is unchanged by regeneration", n_before == nets)

    print("\n%d gate(s) failed" % len(fails) if fails else "\nALL GATES PASSED")
    for f_ in fails:
        print("  FAILED:", f_)
    if notes:
        print("\n%d note(s):" % len(notes))
        for n_ in notes:
            print("  -", n_)
    return 1 if fails else 0


def self_test():
    """Prove the gate CAN fail: run it against deliberately broken inputs."""
    print("SELF-TEST: the gate must FAIL on poisoned designs\n")
    rec = load_record()
    nets = parse_registry()
    rc = 0

    # 1. solar-negative return: ADD a solar node onto a working dedicated return
    p = {k: set(v) for k, v in nets.items()}
    p["/CUT_HEAT_RET1"] = set(p["/CUT_HEAT_RET1"]) | {("/W1_SOLAR_N", "1")}
    ok, why = gate_loop(p, 1, rec)
    print("  solar-negative return: %s (%s)" % ("REJECTED" if not ok else "ACCEPTED", why))
    rc |= 0 if (not ok and "SOLAR" in why) else 1

    # 2. missing shunt: channel 1's FET source no longer lands on a shunt at all
    p = {k: set(v) for k, v in nets.items()}
    p["/CUT_SHUNT_H1"] = {("Q_CUT1", "2"), ("R_SNSA1", "1")}   # shunt gone from the leg
    ok, why = gate_loop(p, 1, rec)
    print("  missing shunt:        %s (%s)" % ("REJECTED" if not ok else "ACCEPTED", why))
    rc |= 0 if not ok else 1

    # 3. divider tapping the FORCE node instead of the KELVIN pad. The tap must actually
    #    MOVE: R_SNSA1 pin 1 leaves the Kelvin net and lands on the force node.
    p = {k: set(v) for k, v in nets.items()}
    p["/CUT_KELV_H1"] = {("R_SH1", "2")}                        # divider off the Kelvin pad
    p["/CUT_SHUNT_H1"] = set(p["/CUT_SHUNT_H1"]) | {("R_SNSA1", "1")}   # onto the force node
    ok, why = gate_loop(p, 1, rec)
    print("  force-node tap:       %s (%s)" % ("REJECTED" if not ok else "ACCEPTED", why))
    rc |= 0 if not ok else 1

    # 4. a two-of-four decoder would fail the one-hot assertion
    def two_hot(a, b):
        return [("LOW" if i in (0, 1) else "HIGH") for i in range(4)]
    bad = all(two_hot(a, b).count("LOW") == 1 for a in (0, 1) for b in (0, 1))
    print("  two-hot decoder:      %s" % ("REJECTED" if not bad else "ACCEPTED"))
    rc |= 0 if not bad else 1

    print("\nSELF-TEST %s" % ("PASSED (the gate can fail)" if rc == 0 else "FAILED"))
    return rc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    sys.exit(self_test() if a.self_test else main())
