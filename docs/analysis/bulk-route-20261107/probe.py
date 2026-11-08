#!/usr/bin/env python3
"""Enumerate native unconnected records and resolve each endpoint to real board geometry.

No inference: every number printed here is read back from the board through pcbnew or from
the native kicad-cli DRC JSON. Used to decide per-net routing targets before any copper is
written.
"""
import json
import os
import re
import sys

import pcbnew

UM = 1_000_000.0
HERE = os.path.dirname(os.path.abspath(__file__))


def load(board_path):
    b = pcbnew.LoadBoard(board_path)
    if b is None:
        raise SystemExit(f"REFUSED: cannot load {board_path}")
    return b


def pad_index(b):
    """(ref, num) -> list of (layer names, rect mm, net). LIST, never dict: a stacked
    two-face land is two pads with one number (targeted-pair-routing.md §0)."""
    out = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            n = p.GetNet()
            ls = p.GetLayerSet()
            lyr = tuple(pcbnew.LayerName(x) for x in ls.Seq()
                        if x in (pcbnew.F_Cu, pcbnew.B_Cu))
            bb = p.GetBoundingBox()
            rect = (bb.GetX() / UM, bb.GetY() / UM,
                    (bb.GetX() + bb.GetWidth()) / UM, (bb.GetY() + bb.GetHeight()) / UM)
            out.setdefault((ref, p.GetNumber() or ""), []).append(
                {"layers": lyr, "rect": rect, "net": n.GetNetname() if n else "",
                 "code": n.GetNetCode() if n else 0, "attr": p.GetAttribute(),
                 "drill": p.GetDrillSize().x / UM})
    return out


PAT_PAD = re.compile(r"^(?:PTH )?[Pp]ad (\S+) \[(.*?)\] of (\S+)(?: on (\S+))?")
PAT_TRACK = re.compile(r"^Track \[(.*?)\] on (\S+), length ([\d.]+) mm")
PAT_VIA = re.compile(r"^Via \[(.*?)\] on (\S+) - (\S+)")
PAT_ZONE = re.compile(r"^Zone '(\S+)' \[(.*?)\] on (\S+), priority (\d+)")


def resolve(desc, pads):
    if m := PAT_PAD.match(desc):
        num, net, ref, layer = m.groups()
        ents = pads.get((ref, num), [])
        return {"kind": "pad", "ref": ref, "num": num, "net": net, "layer": layer,
                "cands": ents}
    if m := PAT_TRACK.match(desc):
        net, layer, length = m.groups()
        return {"kind": "track", "net": net, "layer": layer, "length": float(length)}
    if m := PAT_VIA.match(desc):
        net, l1, l2 = m.groups()
        return {"kind": "via", "net": net, "layers": [l1, l2]}
    if m := PAT_ZONE.match(desc):
        name, net, layer, prio = m.groups()
        return {"kind": "zone", "name": name, "net": net, "layer": layer, "prio": int(prio)}
    return {"kind": "unknown", "raw": desc}


def main():
    board_path = sys.argv[1]
    drc_path = sys.argv[2]
    d = json.load(open(drc_path))
    u = d["unconnected_items"]
    b = load(board_path)
    pads = pad_index(b)

    # locate the physical item nearest a DRC-reported position, for tracks/vias/zones
    tracks = []
    for t in b.GetTracks():
        if "VIA" in str(type(t)):
            p = t.GetPosition()
            tracks.append({"kind": "via", "net": t.GetNetname() or "?",
                           "xy": (p.x / UM, p.y / UM),
                           "w": t.GetWidth(pcbnew.F_Cu) / UM,
                           "drill": t.GetDrillValue() / UM,
                           "layers": tuple(pcbnew.LayerName(x) for x in t.GetLayerSet().Seq()
                                           if x in (pcbnew.F_Cu, pcbnew.B_Cu)),
                           "uuid": t.m_Uuid.AsString()})
        else:
            tracks.append({"kind": "track", "net": t.GetNetname() or "?",
                           "layer": pcbnew.LayerName(t.GetLayer()),
                           "a": (t.GetStart().x / UM, t.GetStart().y / UM),
                           "b": (t.GetEnd().x / UM, t.GetEnd().y / UM),
                           "w": t.GetWidth() / UM, "uuid": t.m_Uuid.AsString()})

    def nearest(kind, net, pos, layer=None):
        best, bd = None, 1e9
        for t in tracks:
            if t["kind"] != kind or t["net"] != net:
                continue
            if layer and t.get("layer") not in (None, layer):
                continue
            d = (min(abs(t["a"][0] - pos[0]) + abs(t["a"][1] - pos[1]),
                     abs(t["b"][0] - pos[0]) + abs(t["b"][1] - pos[1]))
                 if kind == "track" else
                 abs(t["xy"][0] - pos[0]) + abs(t["xy"][1] - pos[1]))
            if d < bd:
                best, bd = t, d
        return best, bd

    out = []
    by_net = {}
    for i, rec in enumerate(u, 1):
        items = rec["items"]
        row = {"n": i, "severity": rec.get("severity"), "type": rec["type"], "ends": []}
        for it in items:
            r = resolve(it["description"], pads)
            r["desc"] = it["description"]
            r["pos"] = (it["pos"]["x"], it["pos"]["y"])
            r["uuid"] = it["uuid"]
            if r["kind"] in ("track", "via"):
                t, dist = nearest(r["kind"], r["net"], r["pos"], r.get("layer"))
                r["phys"] = t
                r["match_dist"] = round(dist, 4)
            row["ends"].append(r)
        nets = sorted({e["net"] for e in row["ends"] if "net" in e})
        row["nets"] = nets
        out.append(row)
        for n in nets:
            by_net.setdefault(n, []).append(i)

    print(f"# {len(out)} unconnected records; {len(by_net)} nets")
    for n in sorted(by_net):
        recs = by_net[n]
        print(f"\n== {n}  ({len(recs)} record(s): {recs})")
        for r in out:
            if r["n"] not in recs:
                continue
            print(f"  R{r['n']:02d} {r['type']}")
            for e in r["ends"]:
                line = f"    - {e['desc']}"
                if e["kind"] == "pad":
                    for c in e["cands"]:
                        line += (f"\n        pad layers={c['layers']} rect=({c['rect'][0]:.3f},"
                                 f"{c['rect'][1]:.3f})-({c['rect'][2]:.3f},{c['rect'][3]:.3f}) "
                                 f"attr={c['attr']} drill={c['drill']:.3f}")
                    if not e["cands"]:
                        line += "\n        !! NO PAD MATCH"
                if e["kind"] == "track" and e.get("phys"):
                    p = e["phys"]
                    line += (f"\n        phys a=({p['a'][0]:.3f},{p['a'][1]:.3f}) "
                             f"b=({p['b'][0]:.3f},{p['b'][1]:.3f}) w={p['w']:.3f} "
                             f"drcpos_dist={e['match_dist']}")
                if e["kind"] == "via" and e.get("phys"):
                    p = e["phys"]
                    line += (f"\n        phys xy=({p['xy'][0]:.3f},{p['xy'][1]:.3f}) "
                             f"w={p['w']:.3f} drill={p['drill']:.3f} "
                             f"drcpos_dist={e['match_dist']}")
                print(line)
    json.dump(out, open(os.path.join(HERE, "opens-resolved.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
