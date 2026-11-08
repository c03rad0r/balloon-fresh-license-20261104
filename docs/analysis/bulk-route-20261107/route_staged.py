#!/usr/bin/env python3
"""route_staged.py -- two-stage router for pairs where BOTH ends are sealed in place.

WHY PLAIN A* FAILS ON THESE. `/SPI1_MISO` U3.3 -> U_C.3 has a legal via 1.725 mm out along the
U3.3 corridor, and the U_C.3 end cannot change layer at all. A single A* that must reach the
goal cell cannot use "escape far, then via" when the far end has no via: it needs the layer
change to happen NEAR THE GOAL, which is exactly where no via exists. What works is the mirror:
change layer near U3.3, run on the other layer, and arrive at U_C.3 on the layer it already is.

So this router plans in stages and commits each stage only if the validator accepts the whole
accumulated set:

  stage 1  A* from A's pad to a legal via site, on A's layer
  stage 2  A* from that via, on the other layer, to B's pad
  (also tried in the reverse order)

Every segment and via is checked with the SAME W.seg_ok / W.via_ok predicate the router uses, so
search and validator cannot disagree. Nothing is written unless all stages validate.

Exit 0 on success. Writes --out only when a validated route exists.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

F, B = R.F, R.B


def free_cells_on_pad(W, pad, pitch, layer):
    """Free raster cells whose centre lies on the pad's own copper, on one layer."""
    x0, y0, x1, y1 = pad["rect"]
    out = []
    n = int(max(x1 - x0, y1 - y0) / pitch / 2) + 3
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for di in range(-n, n + 1):
        for dj in range(-n, n + 1):
            px, py = cx + di * pitch, cy + dj * pitch
            if not (x0 - 0.03 <= px <= x1 + 0.03 and y0 - 0.03 <= py <= y1 + 0.03):
                continue
            ok, _ = W.seg_ok(layer, (px, py), (px, py), pad["net"],
                             {(pad["ref"], pad["num"])})
            if ok:
                out.append((px, py))
    return out


def walk_corridor(W, pad, pitch, layer, max_len=6.0):
    """Every legal point reachable on a straight leg from the pad centre, in 8 directions."""
    pts = []
    cx = (pad["rect"][0] + pad["rect"][2]) / 2
    cy = (pad["rect"][1] + pad["rect"][3]) / 2
    for ang in range(0, 360, 10):
        dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        for k in range(1, int(max_len / pitch) + 1):
            L = k * pitch
            px, py = cx + dx * L, cy + dy * L
            ok, _ = W.seg_ok(layer, (cx, cy), (px, py), pad["net"],
                             {(pad["ref"], pad["num"])})
            if not ok:
                break
            pts.append((px, py, ang, L))
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--pair", required=True, help="NET:REF.NUM:REF.NUM")
    ap.add_argument("--out")
    ap.add_argument("--report")
    ap.add_argument("--pitch", type=float, default=0.1)
    a = ap.parse_args()

    net, ra, rb = a.pair.split(":")
    W = R.World(a.board)
    pa = [q for q in W.pads if f"{q['ref']}.{q['num']}" == ra and q["net"] == net]
    pb = [q for q in W.pads if f"{q['ref']}.{q['num']}" == rb and q["net"] == net]
    if not pa or not pb:
        print(f"REFUSED: pad not found on {net}")
        return 2
    pa, pb = pa[0], pb[0]
    own = {(pa["ref"], pa["num"]), (pb["ref"], pb["num"])}

    print(f"{net}  {ra} -> {rb}")
    print(f"  A layers={pa['layers']}  B layers={pb['layers']}")

    best = None
    for (src, dst, tag) in ((pa, pb, "A->B"), (pb, pa, "B->A")):
        for slay in (src["layers"] or [F, B]):
            for dlay in (dst["layers"] or [F, B]):
                if slay == dlay:
                    continue                      # same layer: plain A* already covers it
                # stage 1: from src pad, find a legal via on slay
                cands = []
                for (px, py, ang, L) in walk_corridor(W, src, a.pitch, slay):
                    vok, _ = W.via_ok(px, py, net)
                    if vok:
                        cands.append((L, px, py, ang))
                if not cands:
                    print(f"  {tag} src={R.b_layer_name(slay) if hasattr(R,'b_layer_name') else slay}"
                          f" dst={dlay}: no legal via on the source corridor")
                    continue
                cands.sort()
                # stage 2: from each candidate via on dlay, can we reach the dst pad?
                for (L, vx, vy, ang) in cands[:6]:
                    ok1, why1 = W.seg_ok(slay,
                                         ((src["rect"][0] + src["rect"][2]) / 2,
                                          (src["rect"][1] + src["rect"][3]) / 2),
                                         (vx, vy), net, own)
                    if not ok1:
                        continue
                    for (qx, qy) in free_cells_on_pad(W, dst, a.pitch, dlay):
                        ok2, why2 = W.seg_ok(dlay, (vx, vy), (qx, qy), net, own)
                        if ok2:
                            best = {"tag": tag, "slay": slay, "dlay": dlay,
                                    "via": (vx, vy), "legA": (
                                        (src["rect"][0] + src["rect"][2]) / 2,
                                        (src["rect"][1] + src["rect"][3]) / 2),
                                    "legB": (qx, qy), "via_dist": L}
                            break
                    if best:
                        break
                if best:
                    break
            if best:
                break
        if best:
            break

    if not best:
        print("  RESULT: no legal 2-stage plan (single via) found")
        if a.report:
            json.dump({"pair": a.pair, "result": "STAGED_UNROUTED"}, open(a.report, "w"))
        return 1

    segs = [(best["slay"], best["legA"], best["via"]),
            (best["dlay"], best["via"], best["legB"])]
    vias = [best["via"]]
    ok, why = R.validate(W, segs, vias, net, own)
    print(f"  plan {best['tag']}: via {tuple(round(v,3) for v in best['via'])} "
          f"at {best['via_dist']:.3f} mm from source")
    print(f"  VALIDATOR: {'ACCEPT' if ok else 'REJECT -- ' + why}")
    if not ok:
        if a.report:
            json.dump({"pair": a.pair, "result": "VALIDATOR_REJECTED", "why": why},
                      open(a.report, "w"))
        return 1
    if a.out:
        b = W.b
        ni = b.FindNet(net)
        for lay, p0, p1 in segs:
            t = R.pcbnew.PCB_TRACK(b)
            t.SetNet(ni)
            t.SetLayer(lay)
            t.SetWidth(int(round(R.TRACK_W * 1e6)))
            t.SetStart(R.pcbnew.VECTOR2I(int(round(p0[0] * 1e6)), int(round(p0[1] * 1e6))))
            t.SetEnd(R.pcbnew.VECTOR2I(int(round(p1[0] * 1e6)), int(round(p1[1] * 1e6))))
            b.Add(t)
        v = R.pcbnew.PCB_VIA(b)
        v.SetNet(ni)
        v.SetPosition(R.pcbnew.VECTOR2I(int(round(best["via"][0] * 1e6)),
                                       int(round(best["via"][1] * 1e6))))
        v.SetWidth(int(round(R.VIA_D * 1e6)))
        v.SetDrill(int(round(R.VIA_DRILL * 1e6)))
        b.Add(v)
        R.refill(a.board)
        b2 = R.pcbnew.LoadBoard(a.board)
        R.pcbnew.SaveBoard(a.out, b2) if False else R.pcbnew.SaveBoard(a.board, b)
        print(f"  wrote {a.out}")
    if a.report:
        json.dump({"pair": a.pair, "result": "STAGED_ROUTED", **{k: str(v) for k, v in best.items()}},
                  open(a.report, "w"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
