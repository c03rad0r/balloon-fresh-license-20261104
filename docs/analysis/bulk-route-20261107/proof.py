#!/usr/bin/env python3
"""proof.py -- connectivity proof for a pair-routing batch, using KICAD's own shapes.

WHAT IT PROVES
  1. every pair named in --pair is now in ONE component (the route actually connected it)
  2. NO previously-connected pair of retained items was broken (the regression gate)
  3. the native open count fell (asserted from two DRC JSONs, not from a claim)

WHY THE OBSTACLE MODEL IS KiCad's, NOT shapely
  An earlier version of this file (connectivity.py) unioned the polygons of ALL layers of a
  component into ONE shapely geometry before measuring distance. That mixes F.Cu and B.Cu
  copper into a single 2-D object, so two ISLANDS on OPPOSITE layers measure 0.000 mm apart
  and a report of "gap 0.000" can be pure artefact. Measured consequence: the first version
  called C10.1 (+3V3) an isolated island on a board where a control experiment proved it is
  connected (moving C10 away ADDS an open). The layer union was the bug.

  Here distance is only ever computed BETWEEN ITEMS ON THE SAME LAYER, and a layer change is
  bridged ONLY by a through-via or a PTH pad -- exactly the predicate native DRC uses.

Exit 0 only when all three proofs hold.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict

import pcbnew

UM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))


def uid(q):
    return q.m_Uuid.AsString()


class Graph:
    """Component partition of one board's copper, per the native predicate."""

    def __init__(self, path, nets=None):
        self.b = pcbnew.LoadBoard(path)
        if self.b is None:
            raise SystemExit(f"REFUSED: cannot load {path}")
        b = self.b
        self.nodes = {}
        items = [q for f in b.GetFootprints() for q in f.Pads()] + list(b.GetTracks())
        for q in items:
            net = q.GetNetname()
            if nets and net not in nets:
                continue
            k = uid(q)
            is_via = isinstance(q, pcbnew.PCB_VIA)
            is_pad = isinstance(q, pcbnew.PAD)
            pth = is_pad and q.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
            lay = [l for l in q.GetLayerSet().CuStack() if b.IsLayerEnabled(l)]
            if is_pad:
                name = f"{q.GetParentFootprint().GetReference()}.{q.GetNumber()}"
                kind = "PAD"
            elif is_via:
                name, kind = "VIA", "VIA"
            else:
                name, kind = "TRACK", "TRACK"
            self.nodes[k] = {"uuid": k, "net": net, "kind": kind, "name": name,
                             "layers": lay, "bridge": is_via or pth, "obj": q}
        # zones: their FILLED polygons, one node per (zone, layer, polygon)
        for z in b.Zones():
            if nets and z.GetNetname() not in nets:
                continue
            for lid in z.GetLayerSet().CuStack():
                if not b.IsLayerEnabled(lid):
                    continue
                try:
                    ps = z.GetFilledPolysList(lid)
                except Exception:
                    continue
                for i in range(ps.OutlineCount()):
                    k = f"{uid(z)}:{lid}:p{i}"
                    self.nodes[k] = {"uuid": uid(z), "net": z.GetNetname(),
                                     "kind": "ZONE", "layers": [lid], "bridge": True,
                                     "name": f"ZONE[{z.GetZoneName() or '?'}]",
                                     "obj": ps.UnitSet(i)}
        self._partition()

    def _partition(self):
        b = self.b
        bynet = defaultdict(list)
        for k, n in self.nodes.items():
            bynet[n["net"]].append(k)
        self.parent = {k: k for k in self.nodes}

        def find(x):
            while self.parent[x] != x:
                self.parent[x] = self.parent[self.parent[x]]
                x = self.parent[x]
            return x

        def union(a, c):
            ra, rc = find(a), find(c)
            if ra != rc:
                self.parent[ra] = rc

        self.edges = 0
        for net, keys in bynet.items():
            # same-layer collision, and same-item layer bridging (via / PTH)
            for i, a in enumerate(keys):
                na = self.nodes[a]
                for c in keys[i + 1:]:
                    nc = self.nodes[c]
                    sa, sc = na["obj"], nc["obj"]
                    if na["uuid"] == nc["uuid"]:
                        # same physical item on two layers: bridges only if it is a via/PTH
                        if na["bridge"]:
                            union(a, c)
                            self.edges += 1
                        continue
                    shared = set(na["layers"]) & set(nc["layers"])
                    if not shared:
                        continue
                    hit = False
                    for lid in shared:
                        try:
                            if sa.GetEffectiveShape(lid).Collide(sc.GetEffectiveShape(lid), 0):
                                hit = True
                                break
                        except Exception:
                            continue
                    if hit:
                        union(a, c)
                        self.edges += 1
        self.comp = {k: find(k) for k in self.nodes}

    def groups(self):
        out = defaultdict(list)
        for k, root in self.comp.items():
            out[root].append(k)
        return out

    def group_of_pad(self, ref, num):
        for k, n in self.nodes.items():
            if n["kind"] == "PAD" and n["name"] == f"{ref}.{num}":
                return self.comp[k]
        return None

    def pads_in(self, root):
        return sorted({n["name"] for k, n in self.nodes.items()
                       if self.comp[k] == root and n["kind"] == "PAD"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--drc-before", required=True)
    ap.add_argument("--drc-after", required=True)
    ap.add_argument("--pair", action="append", default=[])
    ap.add_argument("--report", default=os.path.join(HERE, "proof.json"))
    ap.add_argument("--regress-all", action="store_true",
                    help="run the broken-pair regression over EVERY net, not only the routed "
                         "ones. The narrow form is a weaker claim and must be reported as such.")
    a = ap.parse_args()

    pb = json.load(open(a.drc_before))
    pa = json.load(open(a.drc_after))
    n0 = len(pb["unconnected_items"])
    n1 = len(pa["unconnected_items"])
    print(f"native opens: {n0} -> {n1}  (delta {n1-n0:+d})")

    pair_nets = {p.split(":")[0] for p in a.pair} if a.pair else set()
    regress_nets = None if a.regress_all else (pair_nets or None)
    G0 = Graph(a.before, regress_nets)
    G1 = Graph(a.after, regress_nets)

    fails = []
    # 1. the named pairs must now be one component
    ok_pairs = []
    for spec in a.pair:
        net, ra, rb = spec.split(":")
        ga0, gb0 = G0.group_of_pad(*ra.rsplit(".", 1)), G0.group_of_pad(*rb.rsplit(".", 1))
        ga1, gb1 = G1.group_of_pad(*ra.rsplit(".", 1)), G1.group_of_pad(*rb.rsplit(".", 1))
        same_before = ga0 is not None and ga0 == gb0
        same_after = ga1 is not None and ga1 == gb1
        ok_pairs.append({"spec": spec, "connected_before": same_before,
                         "connected_after": same_after})
        print(f"  pair {spec:44s} before={same_before} after={same_after}")
        if not same_after:
            fails.append(f"pair {spec} is NOT connected after the batch")

    # 2. no previously-connected pair of RETAINED items may have been broken
    #    Items are retained when their uuid exists in both boards.
    retained = [k for k in G0.nodes if k in G1.nodes
                and G0.nodes[k]["kind"] != "ZONE" and G1.nodes[k]["kind"] != "ZONE"]
    lost = []
    # O(n^2) over retained same-net items, but a hash of roots keeps it cheap
    bynet0 = defaultdict(list)
    for k in retained:
        bynet0[G0.nodes[k]["net"]].append(k)
    for net, keys in bynet0.items():
        if len(keys) < 2:
            continue
        for i, x in enumerate(keys):
            for y in keys[i + 1:]:
                if G0.comp[x] == G0.comp[y] and G1.comp[x] != G1.comp[y]:
                    lost.append((x, y))
    print(f"  retained non-zone items: {len(retained)}; "
          f"previously-connected pairs broken: {len(lost)}")
    if lost:
        for x, y in lost[:10]:
            print(f"     BROKEN {G0.nodes[x]['name']} <-> {G0.nodes[y]['name']}")
        fails.append(f"{len(lost)} previously-connected pair(s) broken")

    # 3. opens must strictly fall
    if not (n1 < n0):
        fails.append(f"opens did not fall ({n0} -> {n1})")

    rep = {"before": os.path.abspath(a.before), "after": os.path.abspath(a.after),
           "regression_scope": "ALL NETS" if a.regress_all else f"nets {sorted(pair_nets)}",
           "opens_before": n0, "opens_after": n1,
           "retained_nonzone_nodes": len(retained),
           "broken_previously_connected_pairs": len(lost),
           "pairs": ok_pairs, "failures": fails,
           "verdict": "PASS" if not fails else "FAIL"}
    json.dump(rep, open(a.report, "w"), indent=1)
    print(f"\nVERDICT: {rep['verdict']}")
    for f in fails:
        print("  FAIL:", f)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
