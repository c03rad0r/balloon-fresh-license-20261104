#!/usr/bin/env python3
"""Layer-compatibility proof: can a B.Cu track bridge each diode<->J_W pair?

This is NOT a repair and NOT a proposed fix. It is a falsification test of the
claim "a track cannot bridge them / 0 of 9 are routable on a shared layer".

Method
  1. copy the pinned board to a scratch dir (source never opened for write)
  2. add the MINIMUM number of straight B.Cu tracks: one per net, chaining the
     net's pads in pad order. No A*, no optimisation, no obstacle avoidance.
  3. re-run native kicad-cli DRC on the copy with the same project rules
  4. report how many unconnected records closed and what violations were added

Result is reported honestly either way. Straight lines crossing other copper is
expected and is reported in `violations_added`; that is why this proves ONLY
layer compatibility, not routeability.
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(
    REPO,
    "docs/analysis/hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb",
)
WORK = "/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/solar-audit"
COPPER = {pcbnew.F_Cu: "F.Cu", pcbnew.In1_Cu: "In1.Cu",
          pcbnew.In2_Cu: "In2.Cu", pcbnew.B_Cu: "B.Cu"}
SOLAR_N = ["/W1_SOLAR_N", "/W2_SOLAR_N", "/W3_SOLAR_N"]


def solar_records(drc_json):
    with open(drc_json) as fh:
        d = json.load(fh)
    recs = [u for u in d["unconnected_items"] if "SOLAR" in json.dumps(u)]
    return d, recs


def main():
    os.makedirs(WORK, exist_ok=True)
    dst = os.path.join(WORK, "copy.kicad_pcb")
    shutil.copyfile(SRC, dst)
    shutil.copyfile(SRC[:-len(".kicad_pcb")] + ".kicad_pro",
                    os.path.join(WORK, "copy.kicad_pro"))

    # baseline DRC on the copy
    base = os.path.join(WORK, "drc_baseline.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json",
                    "--output", base, "--severity-all", "copy.kicad_pcb"],
                   cwd=WORK, check=False, capture_output=True, text=True)
    d0, r0 = solar_records(base)

    # add one straight B.Cu track between consecutive pads of each solar-N net
    b = pcbnew.LoadBoard(dst)
    added = []
    for net in SOLAR_N:
        chain = []
        seen = set()
        for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
            for p in fp.Pads():
                if p.GetNetname() != net:
                    continue
                key = (fp.GetReference(), p.GetNumber())
                if key in seen:
                    continue
                if "B.Cu" not in [COPPER[l] for l in p.GetLayerSet().CuStack()]:
                    continue
                seen.add(key)
                chain.append(p)
        for a, c in zip(chain[:-1], chain[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(a.GetPosition())
            t.SetEnd(c.GetPosition())
            t.SetLayer(pcbnew.B_Cu)
            t.SetWidth(int(0.2e6))
            t.SetNet(a.GetNet())
            b.Add(t)
            added.append({"net": net, "length_mm": round(pcbnew.ToMM(
                (c.GetPosition() - a.GetPosition()).EuclideanNorm()), 3)})
    pcbnew.SaveBoard(dst, b)

    after = os.path.join(WORK, "drc_bridged.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json",
                    "--output", after, "--severity-all", "copy.kicad_pcb"],
                   cwd=WORK, check=False, capture_output=True, text=True)
    d1, r1 = solar_records(after)

    from collections import Counter
    t0 = Counter(v["type"] for v in d0["violations"])
    t1 = Counter(v["type"] for v in d1["violations"])
    out = {
        "method": "straight B.Cu segments, one per net, no A*; proofs of layer "
                  "compatibility only, NOT routeability",
        "baseline": {"unconnected": len(d0["unconnected_items"]),
                     "violations": len(d0["violations"]),
                     "solar_paired_records": len(r0),
                     "violation_types": dict(t0)},
        "after_straight_bcu_tracks": {
            "unconnected": len(d1["unconnected_items"]),
            "violations": len(d1["violations"]),
            "solar_paired_records": len(r1),
            "violation_types": dict(t1),
        },
        "tracks_added": added,
        "remaining_solar_records": [
            [it["description"] for it in u["items"]] for u in r1],
        "violations_added": dict(t1 - t0),
        "violations_removed": dict(t0 - t1),
    }
    ev = os.path.join(HERE, "evidence")
    os.makedirs(ev, exist_ok=True)
    with open(os.path.join(ev, "solar_bridge.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(json.dumps({k: out[k] for k in
                      ("baseline", "after_straight_bcu_tracks",
                       "violations_added", "violations_removed")},
                     indent=1, sort_keys=True))
    print("\nremaining solar records after bridging:", len(r1))
    for r in out["remaining_solar_records"]:
        print("  ", r)


if __name__ == "__main__":
    main()
