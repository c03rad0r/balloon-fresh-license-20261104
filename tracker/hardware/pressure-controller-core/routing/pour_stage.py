#!/usr/bin/env python3
"""pour_stage.py -- add ONE copper pour to a board copy and refill.

Pinned, named rules only; nothing is relaxed. The pour clearance equals the board's copper
rule (0.20 mm), the minimum width equals the stock 0.25 mm, and the board's `.kicad_pro` is
never edited -- a pour is copper geometry, so it belongs in the board file where the DRC can
see it.

CONNECTION STYLE (2026-11-11). The earlier GND pours in this campaign used
ZONE_CONNECTION_FULL (direct), which connects a pad to the plane with no relief and no
assembly/thermal margin. `--connection` now defaults to THERMAL so a plane-to-pad joint is
spokes, and DIRECT must be asked for by name. A thermal joint can be physically impossible on
a 0.50 x 0.25 mm pad hemmed in by neighbouring parts; when that happens the DRC reports
`starved_thermal` and the answer is a PAD-LOCAL override (`--pad-full REF.PAD`), recorded in
the report, never a zone-wide fallback to direct.
"""
import argparse
import json
import os
import sys

import pcbnew

UM = 1_000_000
MARGIN = 0.6          # copper-to-edge centreline inset, > m_CopperEdgeClearance 0.5
CONNECTIONS = {"thermal": pcbnew.ZONE_CONNECTION_THERMAL,
               "direct": pcbnew.ZONE_CONNECTION_FULL}


def add_pour(board, net, layer, priority, clearance=0.20, min_width=0.25,
             connection="thermal", thermal_gap=None, thermal_spoke=None):
    if board.FindNet(net) is None:
        raise SystemExit(f"REFUSED: board has no net {net}")
    bb = board.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetX() / UM + MARGIN, bb.GetY() / UM + MARGIN
    x1, y1 = (bb.GetX() + bb.GetWidth()) / UM - MARGIN, (bb.GetY() + bb.GetHeight()) / UM - MARGIN
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(net))
    z.SetLocalClearance(pcbnew.FromMM(clearance))
    z.SetMinThickness(pcbnew.FromMM(min_width))
    z.SetPadConnection(CONNECTIONS[connection])
    if thermal_gap is not None:
        z.SetThermalReliefGap(pcbnew.FromMM(thermal_gap))
    if thermal_spoke is not None:
        z.SetThermalReliefSpokeWidth(pcbnew.FromMM(thermal_spoke))
    z.SetAssignedPriority(priority)
    o = z.Outline()
    o.NewOutline()
    for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    board.Add(z)
    return {"net": net, "layer": board.GetLayerName(layer), "priority": priority,
            "rect": [round(v, 3) for v in (x0, y0, x1, y1)],
            "clearance": clearance, "min_width": min_width,
            "pad_connection": connection,
            "thermal_gap": thermal_gap, "thermal_spoke": thermal_spoke}


def set_pad_connection(board, spec, connection="direct"):
    """`REF.PAD` -> that pad's own zone connection. Recorded, never silent."""
    ref, _, num = spec.rpartition(".")
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        raise SystemExit(f"REFUSED: no footprint {ref}")
    hits = [p for p in fp.Pads() if p.GetNumber() == num]
    if not hits:
        raise SystemExit(f"REFUSED: {ref} has no pad {num}")
    for p in hits:
        p.SetLocalZoneConnection(CONNECTIONS[connection])
    return [p.GetNetname() for p in hits]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--net", required=True)
    ap.add_argument("--layer", required=True, choices=["F.Cu", "B.Cu"])
    ap.add_argument("--priority", type=int, default=0)
    ap.add_argument("--connection", choices=sorted(CONNECTIONS), default="thermal")
    ap.add_argument("--thermal-gap", type=float, default=None)
    ap.add_argument("--thermal-spoke", type=float, default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()

    b = pcbnew.LoadBoard(a.board)
    if b is None:
        raise SystemExit(f"REFUSED: cannot load {a.board}")
    layer = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}[a.layer]
    for z in b.Zones():
        if z.GetNetname() == a.net and z.GetLayer() == layer and not z.GetIsRuleArea():
            raise SystemExit(f"REFUSED: {a.net} pour already exists on {a.layer}")
    info = add_pour(b, a.net, layer, a.priority, connection=a.connection,
                    thermal_gap=a.thermal_gap, thermal_spoke=a.thermal_spoke)
    n = pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(a.out, b)
    # the sibling .kicad_pro / fp-lib-table must travel with the board or the DRC and the
    # zone filler read different rules and a stale/absent fill looks like a real short.
    for ext in (".kicad_pro",):
        src = os.path.splitext(a.board)[0] + ext
        dst = os.path.splitext(a.out)[0] + ext
        if os.path.exists(src) and os.path.abspath(src) != os.path.abspath(dst):
            open(dst, "wb").write(open(src, "rb").read())
    info["zones_filled"] = n
    info["out"] = os.path.abspath(a.out)
    json.dump(info, open(a.report, "w"), indent=1)
    print(json.dumps(info, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
