#!/usr/bin/env python3
"""Which .kicad_dru condition FORM can exempt a TRACK that terminates on a J_W land?

The existing exemption (ADR-046/048 lineage, `docs/fab/handoff/hub_board_v9.kicad_dru`)
relaxes `edge_clearance` conditionlessly, which reaches PADS only. `EDGE-EXEMPTION-MECHANISM.md`
measured that **no reference-based condition works** for this test, and reasoned why: the
edge side of each pair is an Edge.Cuts shape with no footprint, so `Reference` cannot answer.

That leaves the question this script answers, for the ADR that would extend the exemption to
TERMINATING TRACKS: **can the condition see a Track at all, and can it be scoped by net?**

Without that measurement the choice would be a guess between "scope it tightly" and "waive
every track", and those have very different blast radii.

METHOD — one board, one run per form, native `kicad-cli pcb drc` after a zone refill:
  A  no dru at all                       -> control count
  B  conditionless edge exemption        -> proves the file loads and the engine runs
  C  A.Type == 'Track'                   -> does Type match a track?
  D  A.Type == 'Track' && A.NetName ...  -> can it be scoped to the solar returns?
  E  A.Reference == 'J_W1' || ...        -> the known-inert reference form, re-confirmed
  F  net-scoped at a SMALLER min         -> a tighter variant, if D works

Writes ONLY into the scratch directory; the board under test is copied, never edited.
"""
import json
import pathlib
import shutil
import subprocess
import sys

UM = 1_000_000
SCRATCH = pathlib.Path.home() / ".hermes/profiles/manager/cache/scratch/solar-fix/dru-forms"

FORMS = {
    "A_none": None,
    "B_conditionless": '(rule "x" (constraint edge_clearance (min 0.00mm)))',
    "C_type_track": """(rule "x"
  (condition "A.Type == 'Track'")
  (constraint edge_clearance (min 0.00mm)))""",
    "D_type_track_solar": """(rule "x"
  (condition "A.Type == 'Track' && (A.NetName == '/W1_SOLAR_N' || A.NetName == '/W2_SOLAR_N' || A.NetName == '/W3_SOLAR_N')")
  (constraint edge_clearance (min 0.00mm)))""",
    "E_reference": """(rule "x"
  (condition "A.Reference == 'J_W1' || A.Reference == 'J_W2' || A.Reference == 'J_W3' || A.Reference == 'J_W4'")
  (constraint edge_clearance (min 0.00mm)))""",
    # The A/B assignment is not documented per test; if a track is presented as B
    # rather than A, an A.Type condition matches nothing. These two forms settle it.
    "F_type_track_B": """(rule "x"
  (condition "B.Type == 'Track'")
  (constraint edge_clearance (min 0.00mm)))""",
    "G_either_side_track": """(rule "x"
  (condition "A.Type == 'Track' || B.Type == 'Track'")
  (constraint edge_clearance (min 0.00mm)))""",
}


def refill_and_drc(board: pathlib.Path):
    """Refill zones then run native DRC. Both are required: an unfilled board has
    stale connectivity and the counts would not be comparable across forms."""
    script = SCRATCH / "_refill.py"
    script.write_text(
        "import sys, pcbnew\n"
        "b = pcbnew.LoadBoard(sys.argv[1])\n"
        "pcbnew.ZONE_FILLER(b).Fill(b.Zones())\n"
        "pcbnew.SaveBoard(sys.argv[1], b)\n")
    r = subprocess.run(["/usr/bin/python3", str(script), str(board)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"refill failed: {r.stderr[-300:]}"
    out = board.with_suffix(".drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", str(board), "--format", "json",
                    "-o", str(out), "--severity-all", "--units", "mm"],
                   capture_output=True, text=True)
    if not out.exists():
        return None, "kicad-cli produced no report"
    d = json.loads(out.read_text())
    edge = [v for v in d.get("violations", [])
            if v.get("type") == "copper_edge_clearance"]
    track_at_edge = [v for v in edge
                     if any("Track" in (it.get("description") or "")
                            for it in v.get("items", []))]
    return {"total_edge": len(edge), "track_at_edge": len(track_at_edge),
            "violations": len(d.get("violations", [])),
            "unconnected": len(d.get("unconnected_items", []))}, None


def main():
    src = pathlib.Path(sys.argv[1])
    SCRATCH.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, rule in FORMS.items():
        d = SCRATCH / name
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        # the dru is auto-loaded by PROJECT name: <stem>.kicad_dru beside the board
        for f in src.parent.glob(src.stem + ".kicad_*"):
            shutil.copy(f, d / f.name)
        board = d / src.name
        shutil.copy(src, board)
        dru = d / (src.stem + ".kicad_dru")
        if rule is not None:
            dru.write_text("(version 1)\n" + rule + "\n")
        elif dru.exists():
            dru.unlink()
        res, err = refill_and_drc(board)
        results[name] = res if res else {"error": err}
        r = results[name]
        if "error" in r:
            print(f"{name:24s} ERROR {r['error']}")
        else:
            print(f"{name:24s} edge={r['total_edge']:3d}  "
                  f"track-at-edge={r['track_at_edge']:3d}  "
                  f"violations={r['violations']:3d}  unconnected={r['unconnected']:3d}")

    (SCRATCH / "forms.json").write_text(json.dumps(results, indent=1))

    base = results.get("A_none", {})
    waived = results.get("B_conditionless", {})
    if base and waived and "error" not in waived and "error" not in base:
        print(f"\nfile loads and rules execute: "
              f"{'YES' if waived['total_edge'] < base['total_edge'] else 'NO'}")
    print(f"results: {SCRATCH / 'forms.json'}")


if __name__ == "__main__":
    sys.exit(main())
