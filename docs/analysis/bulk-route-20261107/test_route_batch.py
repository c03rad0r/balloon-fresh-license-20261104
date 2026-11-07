#!/usr/bin/env python3
"""test_route_batch.py -- POSITIVE CONTROL for route_batch.py's predicate (AGENTS.md 27).

A gate that cannot fail is not a gate. This asserts, on the REAL board, both directions:

  ACCEPT  a stub between two same-net pads inside one open corridor        -> seg_ok True
  REJECT  the same stub shifted 0.10 mm onto a foreign pad                 -> seg_ok False
  REJECT  a stub through the C10 frozen neighbourhood                      -> seg_ok False
  REJECT  a via placed inside a same-net SMD pad (via-in-pad)              -> via_ok False
  REJECT  a stub crossing a J_W cavity edge                                -> seg_ok False
  AGREE   every free raster cell is accepted by the validator              -> agreement_test

Exit 0 only if all pass. Run with the pcbnew-capable interpreter.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew  # noqa: E402
import route_batch as R  # noqa: E402

BOARD = os.path.join(HERE, "candidate", "board.kicad_pcb")


def pads_near(W, net, xy, rad=6.0):
    out = []
    for p in W.pads:
        if p["net"] != net:
            continue
        cx = (p["rect"][0] + p["rect"][2]) / 2
        cy = (p["rect"][1] + p["rect"][3]) / 2
        if math.hypot(cx - xy[0], cy - xy[1]) <= rad:
            out.append(p)
    return out


def main():
    W = R.World(BOARD)
    fails = []

    # ---- ACCEPT: a short same-net stub in the middle of an open area, no foreign copper --
    # Take two same-net pads that are close, and try their connecting centre line.
    trials = [
        ("/F33_VSENSE", (21.0, 8.0), (22.0, 7.8)),
        ("/SPI1_MISO", (11.0, 14.1), (33.8, 14.1)),
    ]
    accepted = 0
    for net, a, b in trials:
        pa = pads_near(W, net, a, 2.0)
        pb = pads_near(W, net, b, 2.0)
        if not pa or not pb:
            continue
        r0 = pa[0]["rect"]
        r1 = pb[0]["rect"]
        p0 = ((r0[0] + r0[2]) / 2, (r0[1] + r0[3]) / 2)
        p1 = ((r1[0] + r1[2]) / 2, (r1[1] + r1[3]) / 2)
        own = {(pa[0]["ref"], pa[0]["num"]), (pb[0]["ref"], pb[0]["num"])}
        ok, why = W.seg_ok(pcbnew.F_Cu, p0, p1, net, own)
        print(f"ACCEPT-probe {net} {p0}->{p1}: ok={ok} why={why}")
        if ok:
            accepted += 1
    if accepted == 0:
        fails.append("no ACCEPT probe passed -- the predicate rejects everything, so it is "
                     "not usable and any 'unroutable' verdict from it is worthless")

    # ---- REJECT 1: a stub that runs straight through a foreign pad ------------------------
    fp = W.b.FindFootprintByReference("U1")
    u1pads = [p for p in W.pads if p["ref"] == "U1" and p["num"] not in ("",)]
    if u1pads:
        tgt = u1pads[len(u1pads) // 2]
        cx = (tgt["rect"][0] + tgt["rect"][2]) / 2
        cy = (tgt["rect"][1] + tgt["rect"][3]) / 2
        ok, why = W.seg_ok(pcbnew.F_Cu, (cx - 2.0, cy), (cx + 2.0, cy), "/EN", set())
        print(f"REJECT-probe through U1.{tgt['num']}: ok={ok} why={why}")
        if ok:
            fails.append(f"predicate ACCEPTED a stub through foreign pad U1.{tgt['num']}")

    # ---- REJECT 2: C10 frozen neighbourhood ---------------------------------------------
    g = R.C10_GUARD
    cx, cy = (g[0] + g[2]) / 2, (g[1] + g[3]) / 2
    ok, why = W.seg_ok(pcbnew.F_Cu, (cx - 0.5, cy), (cx + 0.5, cy), "/EN", set())
    print(f"REJECT-probe inside C10 guard: ok={ok} why={why}")
    if ok:
        fails.append("predicate ACCEPTED copper inside the frozen C10 neighbourhood")

    # ---- REJECT 3: via-in-pad (same net) -------------------------------------------------
    vpads = [p for p in W.pads if p["net"] == "+3V3" and not p["pth"] and p["drill"] == 0]
    if vpads:
        p = vpads[0]
        cx = (p["rect"][0] + p["rect"][2]) / 2
        cy = (p["rect"][1] + p["rect"][3]) / 2
        ok, why = W.via_ok(cx, cy, "+3V3")
        print(f"REJECT-probe via-in-pad {p['ref']}.{p['num']}: ok={ok} why={why}")
        if ok:
            fails.append(f"via_ok ACCEPTED via-in-pad at {p['ref']}.{p['num']}")

    # ---- REJECT 4: crossing a J_W cavity edge -------------------------------------------
    edges = [e for e in W.edge_segs if e[0] == "J_W2"]
    if edges:
        # J_W2 cavity is x 35.75..36.25, y 74.0..80.0 (measured). Cross it.
        ok, why = W.seg_ok(pcbnew.F_Cu, (34.5, 77.0), (37.5, 77.0), "/W2_SOLAR_N", set())
        print(f"REJECT-probe across J_W2 cavity: ok={ok} why={why}")
        if ok:
            fails.append("predicate ACCEPTED a stub across a J_W cavity (ADR-142)")

    # ---- AGREE: raster must never be permissive ----------------------------------------
    own_rects = []
    grid, nx, ny = R.build_raster(W, 0.1, "/EN", own_rects)
    ok, why = R.agreement_test(W, grid, 0.1, "/EN", set(), samples=1500)
    print(f"AGREE-probe free-cell sample: ok={ok} -- {why}")
    if not ok:
        fails.append(f"raster/validator disagree: {why}")

    print()
    if fails:
        for f in fails:
            print("FAIL:", f)
        print(f"{len(fails)} FAILED")
        return 1
    print("ALL PREDICATE CONTROLS PASSED (both directions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
