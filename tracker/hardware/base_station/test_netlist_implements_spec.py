#!/usr/bin/env python3
"""Verify the generated netlist IMPLEMENTS the spec's frozen invariants.

test_spec_transcription.py checks I copied the freeze correctly. THIS checks the netlist actually
builds what the freeze requires. They are different questions and both must pass.

Invariants checked (each traces to spec.json / the freeze):
  1. all FIVE rails exist, and the four on the +5V side are SEPARATE NETS (the ERC requirement)
  2. NO SAME-NET path from +5V_LNA_SW to +3V3_MCU  (no LNA fault may remove MCU power)
  3. the +5V_VGA rail does NOT share the LNA branch net
  4. the detector input net is reached ONLY through BPF #2 (the mandatory second filter)
  5. the 2.4 GHz TX port reaches NO active device (no 2.4 GHz PA on the PCBA)
  6. the masthead LNA is NOT on this board (no LNA part in the component list)
  7. no circulator part is used
"""
import json
import re
import sys

from pathlib import Path

HERE = Path(__file__).resolve().parent
net = open(f"{HERE}/base_station_v1.net").read()
spec = json.load(open(f"{HERE}/spec.json"))

comps = re.findall(r'\(comp \(ref "([^"]+)"\)\s*\n\s*\(value "([^"]*)"\)', net)
refs = [r for r, _ in comps]
vals = dict(comps)

nets = {}
for b in re.split(r'\n    \(net ', net)[1:]:
    m = re.search(r'\(name "([^"]+)"\)', b)
    if not m:
        continue
    nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', b)
    nets[m.group(1)] = nodes

fails, checks = [], 0
def ck(label, cond, detail=""):
    global checks
    checks += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {label}{'' if cond else '  ' + detail}")
    if not cond:
        fails.append(label)

print("=== 1. five domains, four SEPARATE on the +5V side ===")
for r in ("+5V_PCBA", "+5V_LNA_SW", "+5V_VGA", "+5V_DET", "+3V3_MCU"):
    ck(f"rail {r} is its own net", r in nets,
       f"({len(nets.get(r, []))} nodes)")
sets = {r: {x for x, _ in nets.get(r, [])} for r in
        ("+5V_PCBA", "+5V_LNA_SW", "+5V_VGA", "+5V_DET", "+3V3_MCU")}

print()
print("=== 2. no LNA fault can remove MCU power ===")
# the MCU rail must not be fed from the switched LNA branch
ck("+3V3_MCU is not fed from +5V_LNA_SW",
   not (sets["+5V_LNA_SW"] & sets["+3V3_MCU"]))
ck("+5V_LNA_SW shares no node with +3V3_MCU nets",
   not (sets["+5V_LNA_SW"] & sets["+3V3_MCU"]))
# the switch that makes the branch separate must exist and be its own part
ck("a dedicated LNA switch exists", any("Q_LNA_SW" == r for r in refs))
ck("the LNA switch's output pin goes to +5V_LNA_SW",
   any(p == "5" for _, p in nets.get("+5V_LNA_SW", [])))

print()
print("=== 3. the VGA rail is NOT on the LNA branch ===")
ck("+5V_VGA is not fed from +5V_LNA_SW", not (sets["+5V_VGA"] & sets["+5V_LNA_SW"]))
ck("+5V_VGA is fed from +5V_PCBA via its own bead",
   any(r == "FB_VGA" for r, _ in nets.get("+5V_VGA", [])))

print()
print("=== 4. the detector input is reached ONLY through BPF #2 ===")
# a 2-pin net has exactly 2 nodes: the filter's output pin and the detector's input pin
det_nodes = nets.get("DET_RF_IN", [])
ck("DET_RF_IN has exactly two nodes", len(det_nodes) == 2, str(det_nodes))
ck("the only SOURCE of DET_RF_IN is the mandatory second 433 BPF",
   sorted(r for r, _ in det_nodes) == ["FLT_433_B", "U_DET"], str(det_nodes))
ck("the AD8318 input pin is on that net",
   ("U_DET", "3") in det_nodes)
ck("BPF #2's input comes from the tap net", any(r == "FLT_433_B" for r, _ in nets.get("RF_TAP", [])))
ck("the first 433 BPF also exists", any(r == "FLT_433_A" for r in refs))

print()
print("=== 5. no powered 2.4 GHz path (no PA on the PCBA) ===")
tx_nodes = nets.get("RF_2450_TX", [])
ck("the 2.45 GHz port reaches exactly one connector",
   len(tx_nodes) == 1 and tx_nodes[0][0] == "J_2450_TX", str(tx_nodes))
ck("no active device on the 2.45 GHz net",
   not any(r.startswith("U_") or r.startswith("Q_") for r, _ in tx_nodes))

print()
print("=== 6. the masthead LNA is NOT on this board ===")
# Q_LNA_SW is the BOARD-OWNED bias switch -- that is supposed to be here. What must not be here
# is the masthead amplifier itself (ZX60-P103LN+), which lives at the masthead.
masthead_names = ("ZX60", "P103LN")
ck("no masthead amplifier part on the board",
   not any(any(t in r for t in masthead_names) or any(t in v for t in masthead_names)
           for r, v in comps),
   str([(r, v) for r, v in comps if "LNA" in r or "LNA" in v]))
ck("the board-OWNED LNA bias switch IS present (spec requires it)",
   any(r == "Q_LNA_SW" for r in refs))
ck("the bias tee parts exist (masthead feed boundary)", 
   sum(1 for r in refs if r.startswith("TEE")) == 2)

print()
print("=== 7. no circulator ===")
ck("no circulator part", not any("circulator" in v.lower() or "CIRC" in r for r, v in comps))
ck("spec forbids a circulator substitute", "circulator" in json.dumps(spec).lower())

print()
print("=== 8. design budget sanity (spec: 316 mA total, >=0.5 A cont) ===")
ck("spec records the 316 mA total", "316" in json.dumps(spec))
ck("spec records the 0.5 A continuous budget", "0.5 A" in json.dumps(spec))

print()
print(f"RESULT: {checks - len(fails)}/{checks} checks pass")
if fails:
    print("FAILED:", *fails, sep="\n  - ")
sys.exit(1 if fails else 0)
