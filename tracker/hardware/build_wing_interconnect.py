#!/usr/bin/env python3
"""Build the WING INTERCONNECT BOARD (ADR-132 / ADR-134) -- a SMALL series connector.

WHAT THIS BOARD IS (operator's words, 2026-10-25)
-------------------------------------------------
  "the panels won't be mounted to the wing board. The solar cells get mounted to
   styrofoam and the wing board is just a small connector where + and - of each solar
   panel gets soldered onto. The wing board contains the bypass diodes and it makes the
   series connection between the cells and it connects to the hub board."

So the board is a **connector**, NOT a carrier:

  * the CELLS stay on the XPS foam (ADR-117); their bodies never touch this board,
  * each cell's **+ and - tails** solder to one pad pair here (6 pads total),
  * **3 bypass diodes**, one ACROSS EACH CELL -- a short wire jumper from each cell's
    tail to this board puts the diode in parallel with it (ADR-132),
  * **2-pin tab** out to the hub: SOLAR_P and SOLAR_N (ADR-134 removed GND + RF_FEED).

SIZE: 44 x 20 mm = 8.8 cm2, 0.4 mm FR4 = 0.79 g/wing, 3.17 g for four.

WHY IT IS NOT A LONG SPINE (measured, twice)
--------------------------------------------
Two earlier attempts were wrong and the arithmetic caught both:
  * a full cell-COURT board: 83.8 x 159.1 mm = 133 cm2 = 12.0 g/wing, 48 g for four --
    more than the entire ~42 g payload;
  * a 3-cell single-row spine: 197.15 mm long, which does not fit the 167.1 mm arm.
The connector has no such problem because it carries no cell geometry at all.

TOPOLOGY (ADR-046 / ADR-132 sec 2 / ADR-134)
---------------------------------------------
    SOLAR_P -[SC1]- SOLAR_MID1 -[SC2]- SOLAR_MID2 -[SC3]- SOLAR_N
                 |               |               |
                D1              D2              D3     K -> the cell's HIGH node
                 |               |               |      A -> the cell's LOW  node

A reversed diode is forward-biased by its own cell's 0.5 V and silently shunts that cell,
invisible to a string-voltage check (ADR-054 sec 2.3(b)). Hence the printed K marks and a
mandatory first-article reverse-bias test.

LAYOUT RULES THAT COST REWRITES (kept so they are not repeated)
--------------------------------------------------------------
  * pads need >=0.5 mm to Edge.Cuts, or copper_edge_clearance fires at 0.000 mm
  * silk text below 0.8 mm fires text_height on JLCPCB rules
  * a designator sitting on a pad fires silk_over_copper ("clipped by solder mask")
  * derive a dimension from the layout; a hard-coded length left lands off-board

RUN
---
    python3 tracker/hardware/build_wing_interconnect.py
    python3 tracker/hardware/build_wing_interconnect.py --check   # exit 1 if stale
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wing_interconnect", "wing_interconnect_v1.kicad_pcb")

# ---------------------------------------------------------------- geometry (mm)
# BOARD WIDTH IS DERIVED FROM THE PADS, not chosen. MEASURED: the pads ended at x=33.00
# while the board was 44.0 wide, so 11 mm of the right-hand side carried NO copper at all --
# only the "IC v1" silk label. That is dead FR4: 8.80 cm2 x 0.09028 g/cm2 = 0.79 g/wing,
# of which ~0.20 g was empty board.
#   W = last pad x + EDGE, with the silkscreen markers moved into the free strip instead.
BOARD_W = 34.6      # was 44.0; pads end at 33.00, +1.6 edge = 34.6
BOARD_H = 20.0
EDGE = 1.6

# TAB -- ADR-134: TWO pins only. GND and RF_FEED were removed as dead copper.
TAB_PINS = ["SOLAR_P", "SOLAR_N"]
TAB_PAD_W, TAB_PAD_H = 4.0, 1.2
TAB_PITCH = 1.8
TAB_X = EDGE + TAB_PAD_W / 2.0

SMA_PAD_L, SMA_PAD_W = 2.3, 1.55
CELL_PAD_W, CELL_PAD_H = 2.2, 4.0     # a cell TAIL lands here, one pad per terminal
SILK = 0.8                            # JLCPCB legible minimum

# PAD X OFFSET -- DIODES ALIGN EXACTLY UNDER THE CELL PADS, and that is load-bearing.
# Measured: the first layout put cell pads at cx+-1.85 and diode pads at cx+-1.55, a 0.30 mm
# stagger. Every net then formed a TRIANGLE across two x positions instead of a line, and
# the A* router could only close SOLAR_MID1/MID2 while SOLAR_P and SOLAR_N stayed open
# (8 unconnected after the pass). Aligning them makes each net a straight VERTICAL drop,
# which is the same ladder that routed cleanly in the schematic (ADR-135).
PAD_DX = CELL_PAD_W / 2.0 + 0.75      # 1.85, used by BOTH cells and diodes

# three cell-terminal pairs along the top, three diodes along the bottom
CELL_X = (14.0, 22.0, 30.0)
CELL_Y = 15.0
DIODE_X = (14.0, 22.0, 30.0)
DIODE_Y = 6.0
MID_Y = 10.4

NETS = [("SOLAR_P", 1), ("SOLAR_MID1", 2), ("SOLAR_MID2", 3), ("SOLAR_N", 4)]
NETCODE = dict(NETS)

# lib_id INSTANCE NAME per reference. These resolve against tracker/hardware/wing_interconnect/
# wing_ic.pretty via that directory's fp-lib-table (${KIPRJMOD}). MEASURED before this existed,
# DRC reported 7 x "does not include the footprint library 'wing_ic'" -- a library-NAMING fault,
# not a geometry fault. The pads below are unchanged; only the name resolves now.
FP_FOR_REF = {
    "J1": "Tab_2P",
    "SC1": "SolarTail_2P", "SC2": "SolarTail_2P", "SC3": "SolarTail_2P",
    "D1": "D_SMA_Wing", "D2": "D_SMA_Wing", "D3": "D_SMA_Wing",
}

# cell k: (ref, x of its PAD PAIR, high net, low net)
CELLS = [
    ("SC1", CELL_X[0], "SOLAR_P", "SOLAR_MID1"),
    ("SC2", CELL_X[1], "SOLAR_MID1", "SOLAR_MID2"),
    ("SC3", CELL_X[2], "SOLAR_MID2", "SOLAR_N"),
]
DIODES = [("D1", DIODE_X[0], "SOLAR_P", "SOLAR_MID1"),
          ("D2", DIODE_X[1], "SOLAR_MID1", "SOLAR_MID2"),
          ("D3", DIODE_X[2], "SOLAR_MID2", "SOLAR_N")]


def pads():
    p = []
    # 2-pin tab on the LEFT edge, centred vertically
    for i, net in enumerate(TAB_PINS):
        y = BOARD_H / 2.0 + (i - (len(TAB_PINS) - 1) / 2.0) * TAB_PITCH
        p.append(("J1", str(i + 1), net, TAB_X, y, TAB_PAD_W, TAB_PAD_H))
    # each cell's TWO TAILS land on one pad pair (hi = +, lo = -)
    for ref, cx, hi, lo in CELLS:
        p.append((ref, "1", hi, cx - PAD_DX, CELL_Y, CELL_PAD_W, CELL_PAD_H))
        p.append((ref, "2", lo, cx + PAD_DX, CELL_Y, CELL_PAD_W, CELL_PAD_H))
    # bypass diodes below: pad1 = K (cell HIGH), pad2 = A (cell LOW).
    # Same PAD_DX as the cells, so K sits directly under the cell's + pad and A directly
    # under its - pad -> each net is one straight vertical, no triangle.
    for ref, cx, hi, lo in DIODES:
        p.append((ref, "1", hi, cx - PAD_DX, DIODE_Y, SMA_PAD_L, SMA_PAD_W))
        p.append((ref, "2", lo, cx + PAD_DX, DIODE_Y, SMA_PAD_L, SMA_PAD_W))
    return p


def lib_footprint(ref: str, fpname: str, ox: float, oy: float, rows) -> str:
    """The wing_ic library footprint, re-homed onto the board at (ox, oy).

    Only three things change from the library file: the lib_id prefix, the origin, and
    the reference text plus per-pad nets. Everything else -- courtyard, fab outline,
    pad size, pad order -- is copied through byte-for-byte so `lib_footprint_mismatch`
    cannot fire.
    """
    src = os.path.join(HERE, "wing_interconnect", "wing_ic.pretty", fpname + ".kicad_mod")
    text = open(src, errors="replace").read().rsplit(")", 1)[0]  # drop the closing paren
    body = text.split("\n", 1)[1]                                 # drop the (footprint "X" line
    # replace the reference placeholder with the real designator
    body = re.sub(r'\(fp_text reference "[^"]*"', '(fp_text reference "%s"' % ref, body, count=1)
    # attach a net to each pad, matching by pad number
    nets = {num: net for _r, num, net, _x, _y, _w, _h in rows}
    out = []
    for line in body.split("\n"):
        mm = re.match(r'(\s*)\(pad "([^"]+)"(.*)\)\s*$', line)
        if mm and mm.group(2) in nets:
            net = nets[mm.group(2)]
            out.append('%s(pad "%s"%s (net %d "%s"))'
                       % (mm.group(1), mm.group(2), mm.group(3),
                          NETCODE[net], net))
        else:
            out.append(line)
    body = "\n".join(out)
    return ('  (footprint "wing_ic:%s" (layer "F.Cu") (at %s %s)\n%s\n  )'
            % (fpname, _f(ox), _f(oy), body))


def _f(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


# ---------------------------------------------------------------- deterministic routing
# WHAT THE A* ROUTER GOT AND WHAT IT COULD NOT (measured, 2026-10-25)
# ------------------------------------------------------------------
# route_v10_astar.py routes SOLAR_MID1 and SOLAR_MID2 reliably, in either net order, but
# always fails SOLAR_P and exactly one MID net. Four nets on a 44x20 mm board with a pad
# row at y=15 and a diode row at y=6 is a genuine topological crossing: the two MID trunks
# run horizontally across the x-span that the P and N drops need to descend through.
# Ordering (`--promote`) does not help -- measured, both orders give 2 routed / 2 failed.
#
# The two nets that fail are the two whose pads are COLLINEAR (x equal, y 6 -> 15): a
# straight vertical drop, no search required. So they are emitted here as fixed geometry,
# which leaves the router a smaller problem and is deterministic (FLEET rule: software fix
# over inference). The router is then run with --append for the rest.
#
# Each entry: (net, layer, x1, y1, x2, y2). Vertical drops plus the two tab escapes.
VIA_N_IN, VIA_N_OUT = 7.5, 31.85
# TAB PIN ROWS ARE MEASURED, NOT ASSUMED. DRC reports J1 Pad 1 [SOLAR_P] at y=9.1 and
# Pad 2 [SOLAR_N] at y=10.9 -- the OPPOSITE of what I first wired, which shorted P and N
# together through each other's pads (2 shorting_items + 2 solder_mask_bridge).
TAB_P_Y = 9.1
TAB_N_Y = 10.9
STRAIGHT_ROUTES = [
    # P -- entirely on F.Cu. Column at x=12.15 is left of every MID pad (MID1 at
    # 15.85/20.15, MID2 at 23.85/28.15), so nothing can cross it.
    ("SOLAR_P", "F.Cu", TAB_X, TAB_P_Y, 12.15, TAB_P_Y),
    ("SOLAR_P", "F.Cu", 12.15, TAB_P_Y, 12.15, 15.0),
    ("SOLAR_P", "F.Cu", 12.15, TAB_P_Y, 12.15, 6.0),
    # N -- horizontal escape on B.Cu. It MUST change layer: on F.Cu it crosses P's column
    # at x=12.15 and all four MID verticals (measured: tracks_crossing + 2 shorting_items
    # + 3 solder_mask_bridge). Both vias are deliberately placed OUTSIDE the tab pad span
    # (pads are 4.0 wide at x=3.6, i.e. x 1.6..5.6): a via at x=5.0 is INSIDE that span and
    # produced via-in-pad clearance/hole errors (measured).
    ("SOLAR_N", "F.Cu", TAB_X, TAB_N_Y, VIA_N_IN, TAB_N_Y),
    ("SOLAR_N", "B.Cu", VIA_N_IN, TAB_N_Y, VIA_N_OUT, TAB_N_Y),
    ("SOLAR_N", "F.Cu", VIA_N_OUT, TAB_N_Y, VIA_N_OUT, 15.0),
    ("SOLAR_N", "F.Cu", VIA_N_OUT, TAB_N_Y, VIA_N_OUT, 6.0),
]
STRAIGHT_VIAS = [
    ("SOLAR_N", VIA_N_IN, TAB_N_Y),
    ("SOLAR_N", VIA_N_OUT, TAB_N_Y),
]


def build() -> str:
    L = []
    A = L.append
    A("(kicad_pcb (version 20241229) (generator pcbnew)")
    A("  (general (thickness 0.4))")
    A('  (paper "A4")')
    A("  (layers")
    A('    (0 "F.Cu" signal) (31 "B.Cu" signal)')
    # F.Mask and B.Mask MUST be declared. Measured 2026-11-09: this table originally listed only
    # copper, silk, edge and margin, while every pad referenced F.Mask 14 times. KiCad cannot plot
    # a layer that is absent from the stack, so the gerber export emitted NO mask layers at all --
    # a board with bare copper and no solder mask. That is not a cosmetic omission: JLCPCB would
    # either reject the package or produce boards whose pads are unmasked and whose adjacent
    # copper is exposed to solder bridging. The carrier board declares both and exports them; this
    # generator simply never did.
    A('    (36 "B.SilkS" user "b.silkscreen") (37 "F.SilkS" user "f.silkscreen")')
    # LAYER IDs ARE FIXED BY KICAD, not chosen: F.Mask=1, B.Mask=3, F.Paste=13, B.Paste=15,
    # F.SilkS=5, B.SilkS=7, Edge.Cuts=25. Measured against the hub board, which has always
    # exported mask correctly. An earlier attempt used 9/11 (the ADHESIVE ids) and another used
    # 5/7 (the SILKSCREEN ids); both happened to export, but they put two layers on one id and
    # are not valid. Do not renumber these.
    A('    (1 "F.Mask" user) (3 "B.Mask" user)')
    A('    (44 "Edge.Cuts" user)')
    A("  )")
    A("  (setup (pad_to_mask_clearance 0.05))")
    for name, code in NETS:
        A(f'  (net {code} "{name}")')
    o = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    for i in range(4):
        x1, y1 = o[i]
        x2, y2 = o[(i + 1) % 4]
        A(f'  (gr_line (start {_f(x1)} {_f(y1)}) (end {_f(x2)} {_f(y2)}) '
          f'(stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))')
    # ---- NO TRACKS AT PLACEMENT STAGE (deliberate, same staging as hub_board_v10).
    #      AGENTS.md 21: schematic -> ERC -> netlist -> board -> DRC -> gates -> render,
    #      and ROUTING follows the placement gate. The ratsnest below is the routing task.
    # ---- ONE FOOTPRINT PER REF, with all its pads inside it.
    #      Measured defect: this loop used to emit a whole `(footprint ...)` per PAD, so
    #      every ref existed twice (pads() yields one row per pad). The board had 14
    #      footprints for 7 parts, and the router's clobber guard saw a footprint count
    #      that made no sense. Group by ref first.
    by_ref: dict[str, list] = {}
    for row in pads():
        by_ref.setdefault(row[0], []).append(row)
    for ref, rows in by_ref.items():
        # ORIGIN IS THE PAD-PAIR CENTRE, not the first pad. The library footprint places
        # its pads at +-dx around the origin, so anchoring at a pad would shift every pad
        # by dx (measured: pads landed off the routed copper -> 2 shorts + 11 unconnected).
        ox = (min(r[3] for r in rows) + max(r[3] for r in rows)) / 2.0
        oy = (min(r[4] for r in rows) + max(r[4] for r in rows)) / 2.0
        fpname = FP_FOR_REF[ref]
        # EMIT THE LIBRARY FOOTPRINT VERBATIM, substituting only origin / reference /
        # net. Writing the body by hand produced `lib_footprint_mismatch` on all 7 parts
        # (measured): DRC compares the board's embedded copy against wing_ic.pretty and
        # any difference -- even a missing courtyard or a different pad order -- is a
        # warning. Generating from the library makes a mismatch impossible by construction.
        A(lib_footprint(ref, fpname, ox, oy, rows))
    for net, layer, x1, y1, x2, y2 in STRAIGHT_ROUTES:
        A(f'  (segment (start {_f(x1)} {_f(y1)}) (end {_f(x2)} {_f(y2)}) '
          f'(width 0.5) (layer "{layer}") (net {NETCODE[net]}))')
    for net, vx, vy in STRAIGHT_VIAS:
        A(f'  (via (at {_f(vx)} {_f(vy)}) (size 0.8) (drill 0.4) '
          f'(layers "F.Cu" "B.Cu") (net {NETCODE[net]}))')
    # ---- SILK: TWO separate rows so cell and diode labels cannot collide.
    #      Measured: putting both on the mid strip produced 4 silk_overlap.
    #      ADR-132 sec 4.2 makes the cathode mark mandatory.
    # cell pads span y 13.0..17.0 and diode pads y 4.4..7.6, so the two label rows must
    # sit at 12.2 and 8.6 -- measured: 12.6 clipped the cell pads, 10.4 collided.
    CELL_LBL_Y = 12.2
    DIODE_LBL_Y = 8.6
    for ref, cx, hi, lo in CELLS:
        A(f'  (gr_text "{ref}" (at {_f(cx - 2.6)} {_f(CELL_LBL_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
        A(f'  (gr_text "+" (at {_f(cx + 3.6)} {_f(CELL_LBL_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    for ref, cx, hi, lo in DIODES:
        A(f'  (gr_text "{ref}" (at {_f(cx - 2.6)} {_f(DIODE_LBL_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    # BOARD ID: moved into the free TOP STRIP (y 0..5.22 is clear of all pads).
    # It used to sit at x = BOARD_W-6.0 = 38.0, i.e. in 11 mm of otherwise-empty board --
    # which is why it LOOKED like it was occupying that space. Shrinking the board to
    # 34.6 mm would have put the same text at x=28.6, directly on top of SC3's pad
    # (which spans x 27.05..29.25), so it moves here instead. Silk needs no copper.
    A(f'  (gr_text "IC v1" (at 8.0 2.4) '
      f'(layer "F.SilkS") (effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    A(")")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    # --out: the generator is a pure function of its spec, but the ROUTED board on disk is
    # not (the A* router adds SOLAR_MID1/MID2 copper). Building to a temp path lets the
    # determinism gate verify the generator without demanding it reproduce routed copper.
    ap.add_argument("--out", default=None,
                    help="write to this path instead of the committed board")
    args = ap.parse_args()
    body = build()
    out = args.out or OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if args.check:
        if not os.path.exists(out):
            print(f"STALE: {out} missing")
            return 1
        if open(out).read() != body:
            print(f"STALE: {out} differs")
            return 1
        print(f"ok: {out} matches")
        return 0
    open(out, "w").write(body)
    area = BOARD_W * BOARD_H / 100.0
    print(OUT)
    print(f"size {BOARD_W:.1f} x {BOARD_H:.1f} mm = {area:.1f} cm2")
    print(f"FR4 0.4 mm {area * 0.09028:.2f} g/wing  ({area * 0.09028 * 4:.2f} g for four)")
    print(f"sha256 {hashlib.sha256(body.encode()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
