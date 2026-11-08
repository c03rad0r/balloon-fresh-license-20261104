#!/usr/bin/env python3
"""reach_regression.py -- refuse a batch that makes a still-open pair UNREACHABLE.

THE GAP THIS CLOSES, measured. In batch SPI1SCK_UC I closed /SPI1_SCK (35 -> 32 opens) and in
doing so laid a 2.60 mm B.Cu run at x=35.25 that walls /SPI1_MISO and /SPI1_MOSI off from the
rest of the board. Every gate I had passed:

  - native DRC: opens strictly down, violations unchanged       PASSED
  - proof.py:   previously-connected pairs still connected     PASSED
  - via-in-pad: 0 foreign-net overlaps                         PASSED

None of them can see this, because they all check what EXISTS. The damage is to what is still
POSSIBLE. "Opens strictly decreasing" is therefore not sufficient evidence that a batch was
good, and I reported that batch as good.

HOW IT WORKS. Cheap, layer-local flood fill (no via transitions, so no via_ok cost): for every
still-open record, on each layer its pads occupy, ask whether the two pads' free cells are in one
connected region. Run on the BEFORE and AFTER boards. Any pair that was reachable and is now
unreachable is a regression and the batch must be refused.

This is deliberately conservative: it ignores cross-layer paths, so it can only MISS a regression
(by calling a via-dependent pair unreachable on both boards) -- it cannot invent one. A missing
detection is a weaker failure than a false accusation on a board that has no legal vias anyway.

Exit 0 = no regression. Exit 1 = at least one pair was lost.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

PITCH = 0.1


def still_open_pairs(drc_path, board=None):
    """Pairs from a kicad-cli DRC JSON, as (net, "REF.NUM", "REF.NUM").

    DRC pairs a pad with EITHER a pad OR a track. Track endpoints carry no ref/num, so a track
    item is resolved back to the pad it touches, using the board when one is supplied. Without
    that, /SPI1_MISO disappears from the check entirely -- its records pair a PAD with a TRACK,
    not pad-to-pad, and the first version of this tool silently skipped both of them while
    reporting "LOST: 1".
    """
    d = json.load(open(drc_path))
    pads_by_xy = {}
    if board is not None:
        for p in board.pads:
            x0, y0, x1, y1 = p["rect"]
            for px in (x0, (x0 + x1) / 2, x1):
                for py in (y0, (y0 + y1) / 2, y1):
                    pads_by_xy.setdefault((p["net"], round(px, 1), round(py, 1)), []).append(
                        f"{p['ref']}.{p['num']}")

    def snap(net, x, y):
        for r in (0.1, 0.2, 0.3, 0.5, 0.8, 1.2):
            for dx in (-r, 0, r):
                for dy in (-r, 0, r):
                    k = (net, round(x + dx, 1), round(y + dy, 1))
                    if k in pads_by_xy:
                        return pads_by_xy[k][0]
        return None

    out = []
    for u in d["unconnected_items"]:
        items = u["items"]
        if len(items) < 2:
            continue

        def parse(it):
            desc = it["description"]
            net = ""
            if "[" in desc and "]" in desc:
                net = desc.split("[")[1].split("]")[0]
            ref = num = None
            for tok in ("Pad ", "PTH pad ", "NPTH pad "):
                if tok in desc:
                    rest = desc.split(tok, 1)[1]
                    num = rest.split()[0]
                    break
            if " of " in desc:
                ref = desc.split(" of ", 1)[1].split()[0]
                return net, f"{ref}.{num}"
            # a track or via item: resolve its endpoints to pads of the same net
            if "Track" in desc and board is not None:
                pos = it.get("pos") or {}
                x, y = pos.get("x"), pos.get("y")
                if x is not None:
                    hit = snap(net, float(x), float(y))
                    if hit:
                        return net, hit
            return net, None

        n1, e1 = parse(items[0])
        n2, e2 = parse(items[1])
        net = n1 or n2
        if not (net and e1 and e2):
            continue
        if e1 == e2:
            continue
        out.append((net, e1, e2))
    return out


def reachable(W, net, ra, rb, cache, grids):
    """Is (ra, rb) in one connected free region on a shared copper layer?

    The raster is per NET and cached: every pair on a net shares the same copper obstacles, so
    rebuilding it per pair was the reason the first net-driven version ran >15 minutes on 13
    pairs. One raster per net, many pairs.
    """
    key = (net, ra, rb)
    if key in cache:
        return cache[key]
    pa = [q for q in W.pads if f"{q['ref']}.{q['num']}" == ra and q["net"] == net]
    pb = [q for q in W.pads if f"{q['ref']}.{q['num']}" == rb and q["net"] == net]
    if not pa or not pb:
        cache[key] = None            # not checkable (pad missing, zone anchor, track endpoint)
        return None
    pa, pb = pa[0], pb[0]
    shared = [l for l in (pa["layers"] or [R.F, R.B]) if l in (pb["layers"] or [R.F, R.B])]
    if not shared:
        cache[key] = None            # needs a via; out of scope for this conservative check
        return None
    lay = shared[0]
    li = 0 if lay == R.F else 1
    if net not in grids:
        own = {(q["ref"], q["num"]) for q in W.pads if q["net"] == net}
        rects = [q["rect"] for q in W.pads if q["net"] == net]
        grids[net] = (*R.build_raster(W, PITCH, net, rects, own), own)
    grid, nx, ny, own = grids[net]
    ox, oy = W.origin

    def cells(pad):
        x0, y0, x1, y1 = pad["rect"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        out = []
        n = int(max(x1 - x0, y1 - y0) / PITCH / 2) + 15
        for di in range(-n, n + 1):
            for dj in range(-n, n + 1):
                px, py = cx + di * PITCH, cy + dj * PITCH
                if not (x0 - 0.03 <= px <= x1 + 0.03 and y0 - 0.03 <= py <= y1 + 0.03):
                    continue
                i = int(round((px - ox) / PITCH))
                j = int(round((py - oy) / PITCH))
                if 0 <= i < nx and 0 <= j < ny and not grid[li, j, i]:
                    out.append((i, j))
        return out

    start, goal = cells(pa), set(cells(pb))
    if not start or not goal:
        cache[key] = None
        return None
    seen = np.zeros((ny, nx), dtype=bool)
    dq = deque()
    for (i, j) in start:
        if not seen[j, i]:
            seen[j, i] = True
            dq.append((i, j))
    while dq:
        i, j = dq.popleft()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < ny and not grid[li, nj, ni] and not seen[nj, ni]:
                seen[nj, ni] = True
                dq.append((ni, nj))
    res = any(seen[j, i] for (i, j) in goal)
    cache[key] = res
    return res


def net_pairs(drc_path, board, max_pads=20):
    """Pairs to check, for every net a still-open record names.

    TWO SOURCES, because neither alone is sufficient and I measured both failures:

    A. The record's own two items, resolving a TRACK to the nearest pad of the same net. Cheap,
       and it is the only workable source for GND (71 pads -> 2485 pairs).
    B. Every pad pair on the net, for nets with <= max_pads pads. Needed because a record can
       pair a PAD with a TRACK -- /SPI1_MISO does, in both its records -- and then source A
       cannot form a pad pair at all and the net silently drops out of the check. That is
       exactly how the first version reported "LOST: 1" while two nets had actually been cut.

    The 20-pad cut is empirical, not principled: signal nets here have 2-16 pads, GND has 71.
    Every pair is deduped, so a net appearing in both sources is checked once.
    """
    d = json.load(open(drc_path))
    by_net = {}
    for q in board.pads:
        by_net.setdefault(q["net"], []).append(q)

    def resolve(it, net):
        desc = it["description"]
        if " of " in desc and "Pad" in desc:
            num = desc.split("Pad", 1)[1].strip().split()[0]
            ref = desc.split(" of ", 1)[1].split()[0]
            return f"{ref}.{num}"
        pos = it.get("pos") or {}
        x, y = pos.get("x"), pos.get("y")
        if x is None:
            return None
        best, bd = None, 1e9
        for q in by_net.get(net, []):
            x0, y0, x1, y1 = q["rect"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            dd = ((cx - float(x)) ** 2 + (cy - float(y)) ** 2) ** 0.5
            if dd < bd:
                best, bd = f"{q['ref']}.{q['num']}", dd
        return best if bd <= 3.0 else None

    nets = set()
    out, seen = [], set()

    def add(net, e1, e2):
        if not (e1 and e2) or e1 == e2:
            return
        key = (net, *sorted((e1, e2)))
        if key in seen:
            return
        seen.add(key)
        out.append(key)

    for u in d["unconnected_items"]:
        items = u["items"]
        if len(items) < 2:
            continue
        net = ""
        for it in items:
            desc = it["description"]
            if "[" in desc and "]" in desc:
                net = desc.split("[")[1].split("]")[0]
                break
        if not net:
            continue
        nets.add(net)
        add(net, resolve(items[0], net), resolve(items[1], net))     # source A

    for net in sorted(nets):
        pads = by_net.get(net, [])
        if not pads or len(pads) > max_pads:                          # source B, bounded
            continue
        for k in range(len(pads)):
            for m in range(k + 1, len(pads)):
                add(net, f"{pads[k]['ref']}.{pads[k]['num']}",
                    f"{pads[m]['ref']}.{pads[m]['num']}")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--drc-before", required=True)
    ap.add_argument("--drc-after", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()

    Wb = R.World(a.before)
    Wa = R.World(a.after)
    pairs_b = net_pairs(a.drc_before, Wb)
    pairs_a = net_pairs(a.drc_after, Wa)
    print(f"still-open records: before {len(pairs_b)}, after {len(pairs_a)}")

    cb, ca, gb, ga = {}, {}, {}, {}
    lost, gained, skipped = [], [], 0
    for (net, ra, rb) in pairs_b:
        b = reachable(Wb, net, ra, rb, cb, gb)
        if b is None:
            skipped += 1
            continue
        if not b:
            continue
        aft = reachable(Wa, net, ra, rb, ca, ga)
        if aft is False:
            lost.append((net, ra, rb))
    for (net, ra, rb) in pairs_a:
        b = reachable(Wb, net, ra, rb, cb, gb)
        if b is False:
            aft = reachable(Wa, net, ra, rb, ca, ga)
            if aft is True:
                gained.append((net, ra, rb))

    print(f"  reachable-before and checked: {sum(1 for v in cb.values() if v)}")
    print(f"  not checkable (via-dependent / zone anchor / track endpoint): {skipped}")
    print(f"  LOST (reachable before, unreachable after): {len(lost)}")
    for net, ra, rb in lost:
        print(f"    LOST  {net:14s} {ra} <-> {rb}")
    print(f"  gained reachability: {len(gained)}")
    for net, ra, rb in gained:
        print(f"    GAINED {net:14s} {ra} <-> {rb}")

    if a.report:
        json.dump({"lost": lost, "gained": gained, "skipped": skipped,
                   "verdict": "FAIL" if lost else "PASS"}, open(a.report, "w"), indent=1)
    print(f"\nVERDICT: {'FAIL -- this batch destroyed reachability' if lost else 'PASS'}")
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())
