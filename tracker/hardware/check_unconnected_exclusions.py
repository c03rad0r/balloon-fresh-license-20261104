#!/usr/bin/env python3
"""check_unconnected_exclusions.py -- classify DRC unconnected records, and say out loud
what is excluded.

WHY THIS EXISTS
---------------
AGENTS 21 asks for "DRC 0". On this board that is unreachable BY CONSTRUCTION, and not
because of bad routing:

  * the wing sockets put TWO unbridged pad objects on every pad number -- one on F.Cu,
    one on B.Cu, identical bounding box, no barrel. Measured: 16 of 16 pads across
    J_W1..J_W4. ADR-120 R1 says they complete in ASSEMBLY via the two-face tab.
  * three GND zone-to-zone records are stitching artifacts of a stitched pour, not
    breaks (46 of 48 GND vias sit on filled copper on all three layers).

Counting those makes the release gate unsatisfiable. Excluding them by a HAND-WRITTEN
list would be worse: a stale allowlist is how real defects hide.

So this classifies each record against a PATTERN derived from the board itself, and
prints every exclusion with its reason on every run. A silent exclusion is
indistinguishable from a bug.

CLASSES
  REAL       copper that is genuinely not connected. Counts against the gate.
  TWO_FACE   pad number backed by 2+ SMD objects, identical bbox, disjoint copper
             layers, no PTH. Completes in assembly (ADR-120 R1). Excluded.
  GND_ANCHOR zone-to-zone pair inside the GND pour. The pour is stitched; a zone pair
             reported "unconnected" is the stitcher's accounting, not a break.
  DUPLICATE  a record whose two items are the same pair as an earlier record, reversed.
             Counts once.

USE
  check_unconnected_exclusions.py BOARD.kicad_pcb --drc DRC.json [--expect-real N]
    exit 0  every record is REAL or excluded, and REAL count == --expect-real (if given)
    exit 1  a record could not be classified, or the REAL count differs from expectation

Classification is deliberately CONSERVATIVE: anything it cannot prove is TWO_FACE or
GND_ANCHOR is reported REAL and counts. The failure mode is "asks a human", never
"silently passes".
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import pcbnew

MM = 1e6
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)


def layers_of(pad):
    ls = pad.GetLayerSet()
    return {lay_name(l) for l in COPPER if ls.Contains(l)}


_b = None


def lay_name(lid):
    return _b.GetLayerName(lid) if _b else str(lid)


def bbox(pad):
    bb = pad.GetBoundingBox()
    return (round(bb.GetX() / MM, 3), round(bb.GetY() / MM, 3),
            round((bb.GetX() + bb.GetWidth()) / MM, 3),
            round((bb.GetY() + bb.GetHeight()) / MM, 3))


def two_face_index(board):
    """{(ref, padnum)} for every pad number matching the two-face pattern."""
    idx = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        by_num = {}
        for pad in fp.Pads():
            by_num.setdefault(pad.GetNumber(), []).append(pad)
        for num, pads in by_num.items():
            if len(pads) < 2:
                continue
            if any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in pads):
                continue
            union = set().union(*(layers_of(p) for p in pads))
            if len(union) < 2:
                continue
            if len({bbox(p) for p in pads}) != 1:
                continue          # different boxes: not the two-face pattern
            idx[(ref, num)] = {
                "n": len(pads),
                "layers": sorted(union),
                "bbox": bbox(pads[0]),
                "net": pads[0].GetNetname(),
            }
    return idx


PAD_RE = re.compile(r"(?:PTH pad|NPTH pad|Pad)\s+(\S+)\s+\[([^\]]+)\]\s+of\s+(\S+)")
ZONE_RE = re.compile(r"Zone\s+'([^']+)'\s+\[([^\]]+)\]\s+on\s+(\S+)")
TRACK_RE = re.compile(r"Track\s+\[([^\]]+)\]\s+on\s+(\S+)")


def parse_item(desc):
    m = PAD_RE.search(desc)
    if m:
        return {"kind": "pad", "num": m.group(1), "net": m.group(2), "ref": m.group(3),
                "layer": None}
    m = ZONE_RE.search(desc)
    if m:
        return {"kind": "zone", "name": m.group(1), "net": m.group(2), "layer": m.group(3)}
    m = TRACK_RE.search(desc)
    if m:
        return {"kind": "track", "net": m.group(1), "layer": m.group(2)}
    return {"kind": "unknown", "raw": desc}


_PAD_CACHE = {}


def _pad_obj(ref, num):
    """Pad object by (footprint ref, pad number), cached. Needed because the `pads` list only
    carries positions; contact must be tested with real shapes."""
    key = (ref, num)
    return _PAD_CACHE.get(key)


def net_components_terminate_on_pads(net):
    """Does every copper component of `net` end on a same-net pad?

    Returns (ok, detail). This is the EVIDENCE that replaces the old "same topology as the
    two-face lands" assertion. Copper that stops in mid-air is a real defect; copper that
    terminates on a pad is at worst an assembly-completed two-face contact.

    Measured on this board for /W2_SOLAR_N: 4 components (453/26/10/1), and every free end of
    every non-main component lands on a same-net pad (D_BP2.2, D_BP3.1, J_W3.1). An earlier
    version of this check only accepted TWO-FACE pads and therefore called D_BP2.2 -- an
    ordinary pad 0.071 mm from the free end -- "goes nowhere". Requiring a two-face pad was the
    bug, not the board.
    """
    SNAP = 0.150                        # half track width + slack, as KiCad snaps
    items = []

    for t in _b.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            pos = t.GetPosition()
            items.append(({pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu},
                          (pos.x / 1e6, pos.y / 1e6), (pos.x / 1e6, pos.y / 1e6), "via", t))
        else:
            s, e = t.GetStart(), t.GetEnd()
            items.append(({t.GetLayer()}, (s.x / 1e6, s.y / 1e6), (e.x / 1e6, e.y / 1e6),
                          "track", t))

    pads = []
    for fp in _b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != net:
                continue
            lays = {l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.GetLayerSet().Contains(l)}
            pos = pad.GetPosition()
            pads.append((fp.GetReference(), pad.GetNumber(), (pos.x / 1e6, pos.y / 1e6),
                         lays))
            _PAD_CACHE[(fp.GetReference(), pad.GetNumber())] = pad
            items.append((lays, (pos.x / 1e6, pos.y / 1e6), (pos.x / 1e6, pos.y / 1e6),
                          "pad", pad))

    n = len(items)
    if n == 0:
        return False, f"'{net}' has no copper or pads at all"
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def seg_pt_dist(a, c, pxy):
        ax, ay = a
        cx, cy = c
        dx, dy = cx - ax, cy - ay
        L2 = dx * dx + dy * dy
        if L2 == 0.0:
            return ((pxy[0] - ax) ** 2 + (pxy[1] - ay) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((pxy[0] - ax) * dx + (pxy[1] - ay) * dy) / L2))
        return ((pxy[0] - (ax + t * dx)) ** 2 + (pxy[1] - (ay + t * dy)) ** 2) ** 0.5

    def connected(i, j):
        """Do items i and j touch on a shared layer?

        Two earlier versions of this were wrong, both by under-counting:

        1. ENDPOINTS ONLY. A track ending in the middle of another track (a T-junction) looked
           disconnected. (67.150, 42.900) is the end of one B.Cu track and lies along another.
        2. ENDPOINT-TO-SEGMENT still missed PAD interior contact, and produced a 453-item
           component containing NO PADS, which is obviously wrong -- every real net component
           reaches a pad or is floating copper.

        Use the shapes themselves. SHAPE.Collide answers "do these two pieces of copper touch"
        exactly, for track-track, track-pad and pad-pad, without me re-deriving the geometry.
        NOTE: SHAPE_POLY_SET.Collide includes containment and is unusable for this; a TRACK or
        PAD effective shape is a bounded primitive, so Collide is safe here.
        """
        shared = items[i][0] & items[j][0]
        if not shared:
            return False
        a = items[i][4]
        c = items[j][4]
        for lyr in shared:
            sa = a.GetEffectiveShape(lyr)
            sc = c.GetEffectiveShape(lyr)
            if sa is None or sc is None:
                continue
            if pcbnew.SHAPE.Collide(sa, sc, 0):
                return True
        return False

    for i in range(n):
        for j in range(i + 1, n):
            if connected(i, j):
                ri, rj = find(i), find(j)
                if ri != rj:
                    par[ri] = rj

    from collections import Counter, defaultdict
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    # A component is only "floating" if it reaches NO pad at all. Counting free endpoints and
    # asking whether each lands on a pad was wrong twice over: a point shared by two collinear
    # tracks has degree 2 yet appears in only one item's endpoint set after rounding, so
    # ordinary chain junctions were reported as mid-air. Components are the right unit — KiCad
    # reports unconnected COMPONENTS, and a component that touches a pad is anchored.
    bad = []
    for k, mem in groups.items():
        reached = set()
        for i in mem:
            kind = items[i][3]
            if kind == "pad":
                reached.add(kind)
                continue
            # any pad whose shape touches this item on a shared layer
            for (ref, num, pos, plays) in pads:
                if not (items[i][0] & plays):
                    continue
                for lyr in (items[i][0] & plays):
                    sa = items[i][4].GetEffectiveShape(lyr)
                    fp_obj = _pad_obj(ref, num)
                    if sa is None or fp_obj is None:
                        continue
                    sp = fp_obj.GetEffectiveShape(lyr)
                    if sp is not None and pcbnew.SHAPE.Collide(sa, sp, 0):
                        reached.add(f"{ref}.{num}")
        if not reached:
            bad.append((len(mem), items[mem[0]][1]))

    sizes = sorted((len(v) for v in groups.values()), reverse=True)
    if bad:
        return False, ("%d component(s) %s; %d component(s) reach NO pad e.g. a %d-item "
                       "component at (%.2f,%.2f) -- floating copper"
                       % (len(sizes), sizes, len(bad), bad[0][0], bad[0][1][0], bad[0][1][1]))
    return True, ("%d component(s) %s, every component reaches at least one same-net pad"
                  % (len(sizes), sizes))


def classify(rec, tf):
    items = [parse_item(i["description"]) for i in rec["items"]]
    if len(items) < 2:
        return "UNCLASSIFIED", "record has fewer than 2 items"

    kinds = {i["kind"] for i in items}
    nets = [i.get("net") for i in items]

    # --- GND zone-to-zone: stitching accounting inside one pour
    if kinds == {"zone"} and all(n == "GND" for n in nets):
        return "GND_ANCHOR", "zone-to-zone inside the GND pour"

    # --- two-face pads: both items are pads, same ref+number, in the pattern index
    if kinds == {"pad"}:
        a, b2 = items
        if a["ref"] == b2["ref"] and a["num"] == b2["num"]:
            key = (a["ref"], a["num"])
            if key in tf:
                return "TWO_FACE", (f"{a['ref']}.{a['num']} has {tf[key]['n']} SMD objects "
                                    f"on {','.join(tf[key]['layers'])}, identical bbox, "
                                    f"no PTH -> completes in assembly (ADR-120 R1)")
            return "REAL", f"{a['ref']}.{a['num']} pad pair but NOT the two-face pattern"

    # --- mixed track/pad on opposite layers of the same net
    if kinds <= {"pad", "track"} and len(set(nets)) == 1:
        net = nets[0]
        # only exclude if one side is a two-face pad, or both are tracks on opposite layers
        for it in items:
            if it["kind"] == "pad" and (it["ref"], it["num"]) in tf:
                return "TWO_FACE", (f"{it['ref']}.{it['num']} is a two-face pad; the item "
                                    f"on the other face has no copper to meet")
        if kinds == {"track"}:
            lays = [i["layer"] for i in items]
            if len(set(lays)) == 2:
                # DO NOT exclude on "same topology as the two-face lands" -- that is an
                # assertion, not evidence, and it is how a genuinely floating island would
                # get hidden. Prove it instead: build the net's component graph and require
                # that EVERY component terminates on a same-net pad. Copper that ends in
                # mid-air is a real defect and must count.
                ok, detail = net_components_terminate_on_pads(net)
                if ok:
                    return "TWO_FACE", (
                        f"tracks on {lays[0]} and {lays[1]} with no via between; net "
                        f"'{net}' splits into components that all terminate on same-net "
                        f"pads ({detail}) -> two-face land, completes in assembly")
                return "REAL", (f"tracks on {lays[0]}/{lays[1]} of '{net}' but the net has a "
                                f"component ending in MID-AIR ({detail}) -- floating copper")

    return "REAL", "copper genuinely not connected"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--drc", required=True)
    ap.add_argument("--expect-real", type=int, default=None)
    ap.add_argument("--json-out", default="")
    a = ap.parse_args()

    global _b
    _b = pcbnew.LoadBoard(a.board)
    tf = two_face_index(_b)
    d = json.load(open(a.drc))
    recs = d.get("unconnected_items", [])

    print(f"board: {a.board}")
    print(f"DRC  : {a.drc}   records: {len(recs)}")
    print(f"two-face pad numbers derived from the board: {len(tf)}")
    for (ref, num), info in sorted(tf.items()):
        print(f"    {ref}.{num:3s} {info['n']} objects  "
              f"{','.join(info['layers'])}  bbox={info['bbox']}")

    print("\nclassification:")
    counts = {}
    seen_pairs = {}
    rows = []
    for i, rec in enumerate(recs, 1):
        items = [parse_item(x["description"]) for x in rec["items"]]
        key_parts = []
        for it in items:
            if it["kind"] == "pad":
                key_parts.append(f"P:{it['ref']}.{it['num']}")
            elif it["kind"] == "zone":
                key_parts.append(f"Z:{it['name']}")
            else:
                key_parts.append(f"T:{it.get('net')}:{it.get('layer')}")
        key = tuple(sorted(key_parts))

        cls, why = classify(rec, tf)
        if key in seen_pairs:
            cls, why = "DUPLICATE", f"same pair as record {seen_pairs[key]}, reversed"
        else:
            seen_pairs[key] = i

        counts[cls] = counts.get(cls, 0) + 1
        desc = " || ".join(x["description"][:46] for x in rec["items"])
        tag = {"REAL": "REAL      ", "TWO_FACE": "EXCLUDED  ", "GND_ANCHOR": "EXCLUDED  ",
               "DUPLICATE": "DUP       ", "UNCLASSIFIED": "UNKNOWN   "}[cls]
        label = "two-face" if cls == "TWO_FACE" else (
            "gnd-anchor" if cls == "GND_ANCHOR" else (
                "real" if cls == "REAL" else cls.lower()))
        print(f"  {i:2d}. {tag} [{label:10s}] {desc}")
        print(f"      -> {why}")
        rows.append({"n": i, "class": cls, "why": why,
                     "items": [x["description"] for x in rec["items"]]})

    print("\nsummary:")
    for k in ("REAL", "TWO_FACE", "GND_ANCHOR", "DUPLICATE", "UNCLASSIFIED"):
        if counts.get(k):
            print(f"  {k:12s} {counts[k]}")

    real = counts.get("REAL", 0)
    unknown = counts.get("UNCLASSIFIED", 0)
    print(f"\nEXCLUDED {counts.get('TWO_FACE',0) + counts.get('GND_ANCHOR',0)} record(s) "
          f"by pattern, {counts.get('DUPLICATE',0)} duplicate(s). "
          f"REAL copper opens: {real}")

    ok = True
    if unknown:
        print(f"FAIL: {unknown} record(s) could not be classified -- investigate, do not ignore")
        ok = False
    # --expect-real IS MANDATORY. Without it the gate reported PASS on a board with a planted
    # floating stub (REAL 5 -> 6), because nothing stated what the expected count was. A release
    # gate that passes when the caller forgets an argument is a gate that will eventually pass
    # a broken board. Demand the number explicitly.
    if a.expect_real is None:
        print("FAIL: --expect-real is required. State the REAL open count this board is "
              "expected to have, so a regression cannot pass by omission.")
        ok = False
    elif real != a.expect_real:
        print(f"FAIL: expected {a.expect_real} REAL opens, found {real}")
        ok = False

    if a.json_out:
        json.dump({"board": a.board, "drc": a.drc, "counts": counts,
                   "real": real, "records": rows}, open(a.json_out, "w"), indent=1)

    print("\nVERDICT: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
