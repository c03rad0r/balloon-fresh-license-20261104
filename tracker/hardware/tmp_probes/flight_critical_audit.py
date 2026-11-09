"""Is every FLIGHT-CRITICAL net actually connected?

The goal is a board that WORKS AS A FLIGHT BOARD. So the question is not "how many DRC records are
left" -- it is "can the radios talk, and can the MCU talk to the radios".

Everything else is either a DNP part or a flash-time convenience. This audit separates the two, so
effort goes where it changes whether the thing flies.

FLIGHT-CRITICAL = every net touching U1, U3, U_LORA1280, and the power path.
NOT flight-critical = nets whose only other end is a DNP part, or which are flash-time only.
"""
import os
from collections import defaultdict

import pcbnew

MM = 1e6
BD = 'docs/analysis/bulk-route-20261107/work.kicad_pcb'
b = pcbnew.LoadBoard(BD)

DNP = {'U_C', 'U2', 'U5', 'U6', 'C_CAP1', 'C_CAP2',
       'U_CUT1', 'U_CUT2', 'U_CUT3', 'U_CUT4', 'U_HUB_CVT'}
HAND = {'J_W1', 'J_W2', 'J_W3', 'J_W4', 'U3', 'U_LORA1280'}
FLIGHT_PARTS = {'U1', 'U3', 'U_LORA1280', 'U7'}

pads = defaultdict(list)      # net -> [(ref. pad)]
tracks = defaultdict(int)
vias = defaultdict(int)
zones = set()

for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNetname()
        if n:
            pads[n].append((fp.GetReference(), p.GetNumber()))
for t in b.GetTracks():
    n = t.GetNetname()
    if n:
        if t.GetClass() == 'PCB_VIA':
            vias[n] += 1
        else:
            tracks[n] += 1
for z in b.Zones():
    if z.GetNetname():
        zones.add(z.GetNetname())

POWER = {'/VSCAP', '+3V3', 'GND', '/W1_SOLAR_P', '/SCAP_MID', '/W2_SOLAR_N', '/W3_SOLAR_N'}

print('FLIGHT-CRITICAL NETS (touch U1 / U3 / U_LORA1280 / U7, or are power)\n')
flight_bad = []
other_bad = []

for net in sorted(pads):
    refs = {r for r, _ in pads[net]}
    is_flight = bool(refs & FLIGHT_PARTS) or net in POWER
    tr = tracks.get(net, 0)
    vi = vias.get(net, 0)
    zo = net in zones
    has_copper = tr > 0 or vi > 0 or zo
    # a net needs copper if it joins 2+ distinct pads, or 1 pad plus a zone
    need = len(pads[net]) > 1 or (len(pads[net]) == 1 and zo)
    ok = has_copper or not need
    if not ok:
        (flight_bad if is_flight else other_bad).append((net, sorted(refs), len(pads[net])))

print(f'{"net":22s} {"pads":>4s} {"trk":>4s} {"via":>3s} {"zone":>4s}  parts')
for net in sorted(pads):
    refs = {r for r, _ in pads[net]}
    if not (bool(refs & FLIGHT_PARTS) or net in POWER):
        continue
    tr = tracks.get(net, 0)
    vi = vias.get(net, 0)
    zo = 'Y' if net in zones else '-'
    flag = '' if (tr or vi or zo or len(pads[net]) <= 1) else '   <-- NO COPPER'
    print(f'{net:22s} {len(pads[net]):4d} {tr:4d} {vi:3d} {zo:>4s}  '
          f'{",".join(sorted(refs))[:44]}{flag}')

print(f'\n=== FLIGHT-CRITICAL gaps: {len(flight_bad)}')
for net, refs, n in flight_bad:
    print(f'  {net:22s} {n} pads  {refs}')
print(f'\n=== non-flight gaps: {len(other_bad)}')
for net, refs, n in other_bad:
    print(f'  {net:22s} {n} pads  {refs}')

# ---- do the radios have ALL their pins connected?
print('\n=== per-part connectivity (pads with a net vs pads with copper)')
for ref in sorted(FLIGHT_PARTS | DNP | HAND):
    fp = next((f for f in b.GetFootprints() if f.GetReference() == ref), None)
    if fp is None:
        continue
    total = len({p.GetNumber() for p in fp.Pads()})
    netted = sum(1 for p in fp.Pads() if p.GetNetname())
    dangling = [p.GetNumber() for p in fp.Pads()
                if p.GetNetname() and not (tracks.get(p.GetNetname())
                                           or vias.get(p.GetNetname())
                                           or p.GetNetname() in zones)
                and len(pads[p.GetNetname()]) == 1]
    tag = 'FLIGHT' if ref in FLIGHT_PARTS else ('DNP' if ref in DNP else 'HAND')
    print(f'  {ref:11s} {tag:6s} pads={total:2d} netted={netted:2d} '
          f'single-pad-nets={len(dangling)}'
          + (f'  {dangling}' if dangling else ''))
