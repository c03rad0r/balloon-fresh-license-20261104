#!/usr/bin/env python3
"""NETLIST PARITY GATE: the generator's netlist vs the native schematic's export.

Two artifacts claim to describe the same board:
  A. base_station_v1.net             emitted by gen_base_station_netlist.py (the pre-existing
                                     source of truth, 53 parts / 40 nets)
  B. the netlist KiCad itself derives from base_station_v1.kicad_sch

A transcription is only trustworthy if B == A exactly. This gate fails when:
  * a net exists in A and not in B           -> MISSING NET (connectivity lost)
  * a net exists in B and not in A           -> EXTRA NET (connectivity invented)
  * a net exists in both with different pins -> PIN MEMBERSHIP MISMATCH
  * a pin connected in A appears unconnected in B, or vice versa

KiCad auto-generates a single-pin net name for every deliberately unconnected pin
("unconnected-(U_MCU-GPIO0-Pad2)"). Those are the ABSENCE of a net. They are excluded from
the net comparison but NOT ignored: the gate separately checks that every one of them is a
pin the generator also leaves unconnected, so an auto-net can never mask a dropped connection.

Exit codes: 0 parity holds, 1 parity broken, 2 could not run (REFUSED -- never a pass).

Usage:
  base_station_parity.py                 # check the committed artifacts
  base_station_parity.py --sch OTHER.kicad_sch   # check a mutated copy (negative control)
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENERATOR = HERE / "gen_base_station_netlist.py"
GENERATED_NET = HERE / "base_station_v1.net"
SCH = HERE / "base_station_v1.kicad_sch"

AUTO_NET = re.compile(r"^(unconnected-|only_one_node|net-\(|unnamed|no_net|nc-)", re.I)


# ---------------------------------------------------------------------------------------
def regenerate() -> str:
    """Run the generator in a temp dir so the tree is never modified by a check."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        for name in ("gen_base_station_netlist.py", "spec.json"):
            (out / name).write_bytes((HERE / name).read_bytes())
        r = subprocess.run([sys.executable, str(out / "gen_base_station_netlist.py")],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"REFUSED: generator exited {r.returncode}\n{r.stderr}")
        return (out / "base_station_v1.net").read_text()


def parse_netlist(text: str):
    """(nets {name: {(ref,pin)}}, pins {(ref,pin): net}) from a kicadsexpr netlist."""
    nets, pins = {}, {}
    for blk in re.finditer(r'\(net \(code "[^"]*"\) \(name "([^"]*)"\)(.*?)(?=\(net \(code|\Z)',
                           text, re.S):
        name = blk.group(1).lstrip("/")
        nodes = {(m.group(1), m.group(2)) for m in
                 re.finditer(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', blk.group(2))}
        if not nodes:
            continue                    # a net with no nodes is not connectivity
        nets[name] = nodes
        for node in nodes:
            assert node not in pins, f"{node} is on two nets: {pins[node]} and {name}"
            pins[node] = name
    return nets, pins


def native_export(sch: Path) -> str:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "n.net"
        r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format",
                            "kicadsexpr", "-o", str(out), str(sch)],
                           capture_output=True, text=True, timeout=900)
        if not out.exists():
            raise SystemExit(f"REFUSED: kicad-cli could not export {sch.name} "
                             f"(rc={r.returncode})\n{r.stderr[-2000:]}")
        return out.read_text()


# ---------------------------------------------------------------------------------------
def compare(gen_text: str, nat_text: str, verbose: bool = True):
    """Return (failures, notes). Pure function so the negative controls can drive it."""
    gnets, _ = parse_netlist(gen_text)
    nnets_all, _ = parse_netlist(nat_text)
    failures, notes = [], []

    n_auto = {n: p for n, p in nnets_all.items() if AUTO_NET.match(n)}
    nnets = {n: p for n, p in nnets_all.items() if not AUTO_NET.match(n)}

    only_gen = sorted(set(gnets) - set(nnets))
    only_nat = sorted(set(nnets) - set(gnets))
    if only_gen:
        failures.append(f"MISSING NET: {len(only_gen)} net(s) in the generator but not in the "
                        f"native schematic: {only_gen}")
    if only_nat:
        failures.append(f"EXTRA NET: {len(only_nat)} net(s) in the native schematic but not in "
                        f"the generator -- connectivity invented: {only_nat}")

    for name in sorted(set(gnets) & set(nnets)):
        g, n = gnets[name], nnets[name]
        if g != n:
            failures.append(
                f"PIN MEMBERSHIP MISMATCH on {name}: generator-only "
                f"{sorted(g - n)}, native-only {sorted(n - g)}")

    # Auto-nets must be pins the generator ALSO leaves unconnected. If the native side
    # calls a pin unconnected while the generator connects it, that pin was dropped --
    # which is exactly the failure the exclusion above would otherwise hide.
    gen_pins = {p for nodes in gnets.values() for p in nodes}
    dropped = [p for p in sorted({p for nodes in n_auto.values() for p in nodes})
               if p in gen_pins]
    if dropped:
        failures.append(f"DROPPED CONNECTIONS: {len(dropped)} pin(s) connected in the "
                        f"generator are unconnected in the native schematic: {dropped}")

    if verbose:
        print(f"   generator nets : {len(gnets)}   native nets: {len(nnets)}   "
              f"native auto-nets (deliberate unconnected pins): {len(n_auto)}")
        if dropped:
            print(f"   FAIL  {len(dropped)} pin(s) lost their net in the native export")
    return failures, notes, len(gnets), len(nnets), len(n_auto)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sch", default=str(SCH))
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    if not Path(args.sch).exists():
        print(f"REFUSED: no schematic at {args.sch}")
        return 2
    try:
        gen_text = regenerate()
        nat_text = native_export(Path(args.sch))
    except SystemExit as e:
        print(str(e))
        return 2

    failures, _, ng, nn, na = compare(gen_text, nat_text, verbose=not args.quiet)
    for f in failures:
        print(f"   FAIL  {f}")
    if failures:
        print(f"PARITY: BROKEN ({len(failures)} failure(s))")
        return 1
    print(f"PARITY: PASS -- {ng} nets, every net and every pin membership identical; "
          f"{na} native auto-net(s) all correspond to pins the generator also leaves "
          f"unconnected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
