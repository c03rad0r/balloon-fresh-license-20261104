#!/usr/bin/env python3
"""opens_report.py -- for each DRC unconnected record, say what the two ends ARE and whether they
are fitted on the assembled board.

AUTHORITY: KiCad's DRC decides what is open. This script does NOT re-derive connectivity -- two
attempts at that here were wrong (see below) and a connectivity model that disagrees with the
router is worse than no model, because its errors look like clean results.

What it adds over the raw DRC report is only what the DRC report does not say: for every endpoint,
the reference designator and whether that footprint is fitted (DNP / excluded-from-BOM read from the
board's own attributes). That is enough to see which opens touch hardware that will actually be on
the board.

WHY CONNECTIVITY IS NOT RE-COMPUTED HERE (both measured on this board):
  1. CONNECTIVITY_DATA.GetConnectedPads/GetConnectedTracks returned EMPTY sets for every pad under
     pcbnew 9.0.9, so every pad looked isolated -- the check reported a maximally-broken board as
     fine. Silent, and in the most dangerous direction.
  2. Re-implementing union-find over SHAPE.Collide (the primitive the gate uses, and which
     reproduced /W2_SOLAR_N's 464/26 split exactly) still shredded /VSCAP into 11 islands, because
     a net carried by a filled ZONE is joined through the zone's polygons, which are not
     PAD/TRACK objects and so never entered the graph. A plane is a conductor.

So: the DRC's own 11 records are the open set; this script annotates them.

Run: /usr/bin/python3 docs/analysis/opens_report.py <board.kicad_pcb> <drc.json> [--expect-real N]
"""
import argparse
import json
import re
import sys

import pcbnew

COPPER = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]


def fp_state(board):
    """ref -> (fitted, reason) for every footprint on the board."""
    states = {}
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        fit, why = True, ""
        try:
            if fp.IsDNP():
                fit, why = False, "DNP"
        except Exception:
            pass
        if fit:
            try:
                if fp.IsExcludedFromBOM():
                    fit, why = False, "EXCL_BOM"
            except Exception:
                pass
        states[ref] = (fit, why)
    return states


def pad_state(board, states, ref, num):
    """Find a pad's fitted state and layer by (ref, pad number). Returns (fitted, reason, layer)."""
    for fp in board.GetFootprints():
        if fp.GetReference() != ref:
            continue
        for p in fp.Pads():
            if str(p.GetNumber()) == str(num):
                fit, why = states.get(ref, (True, ""))
                lay = p.GetLayerName()
                return fit, why, lay
    return True, "", "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("drc")
    ap.add_argument("--expect-real", type=int, default=None)
    a = ap.parse_args()

    board = pcbnew.LoadBoard(a.board)
    states = fp_state(board)
    d = json.load(open(a.drc))

    # KiCad 9's JSON puts these in a TOP-LEVEL "unconnected_items" array, not inside "violations".
    # Reading only violations[] yields 0 records and a vacuous pass.
    recs = d.get("unconnected_items") or [v for v in d.get("violations", [])
                                          if v.get("type") == "unconnected_items"]
    print(f"board : {a.board}")
    print(f"drc   : {a.drc}")
    print(f"records: {len(recs)}")
    print(f"fitted/unfitted footprints: "
          f"{sum(1 for f, _ in states.values() if f)}/{sum(1 for f, _ in states.values() if not f)}")
    print()

    fitted_opens = []
    for i, v in enumerate(recs, 1):
        items = v.get("items", [])
        nets = set()
        parts = []
        any_fitted = False
        all_fitted = True
        for it in items:
            desc = it.get("description", "?")
            net = (it.get("net") or {}).get("name", "")
            if net:
                nets.add(net)
            # parse "Pad 4 [/SPI2_SCK] of U1 on F.Cu" or "Track [...] on B.Cu"
            m = re.search(r"Pad\s+(\S+)\s+\[[^\]]*\]\s+of\s+(\S+)\s+on\s+(\S+)", desc)
            if m:
                num, ref, lay = m.group(1), m.group(2), m.group(3)
                fit, why = states.get(ref, (True, ""))
                any_fitted = any_fitted or fit
                all_fitted = all_fitted and fit
                tag = "fitted" if fit else why
                parts.append(f"{ref}.{num} ({tag})")
            else:
                parts.append(desc)
                all_fitted = False
        verdict = "TOUCHES FITTED HW" if any_fitted else "DNP-only"
        if any_fitted:
            fitted_opens.append((i, sorted(nets)))
        print(f"{i:2d}. [{verdict}] {' || '.join(parts)}")

    print()
    print(f"records whose endpoints include fitted hardware: {len(fitted_opens)}")
    for i, nets in fitted_opens:
        print(f"   record {i}: {nets}")

    if a.expect_real is not None:
        print()
        print(f"--expect-real {a.expect_real}: this script does NOT re-classify records "
              f"(two-face lands, GND anchors and duplicates are patterns); run "
              f"tracker/hardware/check_unconnected_exclusions.py for that gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
