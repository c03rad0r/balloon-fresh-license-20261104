#!/usr/bin/env python3
"""Measure the wing interconnect board for the JLCPCB support packet.

Everything printed here is read out of the board file through pcbnew; nothing is
transcribed from a document.  Run with the native KiCad Python:

    /usr/bin/python3 tracker/hardware/measure_wing_interconnect.py [--json out.json]
"""
import argparse
import json
import os
import sys

import pcbnew

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOARD = os.path.join(WT, 'tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb')


def mm(v):
    return round(pcbnew.ToMM(v), 4)


def edge_cuts_centreline(board):
    """Bounding box of the Edge.Cuts CENTRELINE.

    GetBoardEdgesBoundingBox() inflates by the line width (0.1 mm default), which is
    why the old README says 34.7 x 20.1 for a 34.6 x 20.0 board.  A fabricator
    quotes the centreline, so measure the centreline.
    """
    xs, ys = [], []
    segs, arcs, circles, rects, polys, other = 0, 0, 0, 0, 0, 0
    for d in board.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts:
            continue
        kind = d.GetShape()
        if kind == pcbnew.SHAPE_T_SEGMENT:
            segs += 1
            xs += [mm(d.GetStart().x), mm(d.GetEnd().x)]
            ys += [mm(d.GetStart().y), mm(d.GetEnd().y)]
        elif kind == pcbnew.SHAPE_T_ARC:
            arcs += 1
            # centre + endpoints; the true extreme of an arc can lie between
            # endpoints, so sample the arc.
            for t in range(0, 101):
                p = d.GetStart()
                try:
                    pt = d.GetPointAlong(t / 100.0)
                except Exception:
                    pt = None
                if pt is not None:
                    xs.append(mm(pt.x))
                    ys.append(mm(pt.y))
            xs.append(mm(p.x))
            ys.append(mm(p.y))
        elif kind == pcbnew.SHAPE_T_CIRCLE:
            circles += 1
            c, r = d.GetCenter(), d.GetRadius()
            xs += [mm(c.x) - mm(r), mm(c.x) + mm(r)]
            ys += [mm(c.y) - mm(r), mm(c.y) + mm(r)]
        elif kind == pcbnew.SHAPE_T_RECT:
            rects += 1
            for pt in (d.GetStart(), d.GetEnd()):
                xs.append(mm(pt.x))
                ys.append(mm(pt.y))
        elif kind == pcbnew.SHAPE_T_POLY:
            polys += 1
            pts = d.GetPolyShape()
            if pts.OutlineCount():
                for pt in pts.Outline(0).CPoints():
                    xs.append(mm(pt.x))
                    ys.append(mm(pt.y))
        else:
            other += 1
    return dict(
        xmin=min(xs), xmax=max(xs), ymin=min(ys), ymax=max(ys),
        width=round(max(xs) - min(xs), 4), height=round(max(ys) - min(ys), 4),
        segments=segs, arcs=arcs, circles=circles, rects=rects, polys=polys, other=other,
        item_count=segs + arcs + circles + rects + polys + other,
    )


def pad_report(board):
    out = []
    for fp in board.GetFootprints():
        pos = fp.GetPosition()
        row = dict(ref=fp.GetReference(), value=fp.GetValue(),
                   fpid=str(fp.GetFPID().GetLibItemName()),
                   layer=board.GetLayerName(fp.GetLayer()),
                   x=mm(pos.x), y=mm(pos.y),
                   rotation=round(fp.GetOrientation().AsDegrees() % 360.0, 3),
                   pads=[])
        for p in fp.Pads():
            pp = p.GetPosition()
            # pad 1 offset from the footprint anchor, in the footprint's own frame
            dx = mm(pp.x - pos.x)
            dy = mm(pp.y - pos.y)
            th = fp.GetOrientation().AsRadians()
            cos, sin = __import__('math').cos(th), __import__('math').sin(th)
            # un-rotate the offset so the number is footprint-local
            lx = round(dx * cos + dy * sin, 4)
            ly = round(-dx * sin + dy * cos, 4)
            row['pads'].append(dict(
                number=p.GetNumber(), net=p.GetNetname(), type=str(p.GetAttribute()),
                x=mm(pp.x), y=mm(pp.y), local_dx=lx, local_dy=ly,
                size_x=mm(p.GetSize().x), size_y=mm(p.GetSize().y),
                layers=[board.GetLayerName(l) for l in p.GetLayerSet().Seq()],
            ))
        out.append(row)
    return out


def vias(board):
    return [dict(x=mm(t.GetPosition().x), y=mm(t.GetPosition().y),
                 drill=mm(t.GetDrill()), dia=mm(t.GetWidth()),
                 layers=f'{board.GetLayerName(t.TopLayer())}->{board.GetLayerName(t.BottomLayer())}')
            for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json')
    args = ap.parse_args()

    b = pcbnew.LoadBoard(BOARD)
    tracks = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    segs = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
    data = dict(
        board_path=os.path.relpath(BOARD, WT),
        thickness_mm=b.GetDesignSettings().GetBoardThickness() / 1e6,
        copper_layers=b.GetCopperLayerCount(),
        edge=edge_cuts_centreline(b),
        tracks=len(segs), vias=vias(b),
        footprints=pad_report(b),
        drawing_counts={b.GetLayerName(l): sum(1 for d in b.GetDrawings() if d.GetLayer() == l)
                        for l in b.GetEnabledLayers().Seq()},
    )
    print(json.dumps(data, indent=2))
    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(data, fh, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
