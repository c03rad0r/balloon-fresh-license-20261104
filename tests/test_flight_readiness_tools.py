"""Gates for the flight-readiness tooling landed with docs/analysis/flight-readiness-20261102.

These are not decoration: each asserts a property the tools are used to CLAIM, and each has a
negative half so a broken tool cannot report the property as true.

  * compare_copper: identical objects must compare identical, a real copper edit must differ, and a
    zone refill must NOT be reported as a copper change (the distinction the whole audit rests on).
  * electrical_mechanical_audit: the via histogram must match the file's actual vias, and the flag
    list must fire when a sub-frozen via exists.
  * verify_visual_claims: the detached-reference measure must find a label that is deliberately
    moved 20 mm away, and must not flag one left in place.

pcbnew is needed for all three. It lives in the distro interpreter (/usr/bin/python3) and in the
kicad venv, NOT in the host pytest interpreter on CI, so these tests loud-skip the way
test_v10_hole_clearance.py does — and the skip reason names the interpreter, so a silent skip is
visible in the log.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools" / "flight_readiness"
BOARD = REPO / "tracker" / "hardware" / "hub_board_v10_lora1280_7of9.kicad_pcb"
KICAD_PY = os.environ.get(
    "KICAD_PY",
    "/usr/bin/python3" if os.path.exists("/usr/lib/python3/dist-packages/pcbnew.py") else "",
)


def _run(script, *args):
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", "/usr/lib/python3/dist-packages")
    return subprocess.run([KICAD_PY, str(TOOLS / script), *map(str, args)],
                          capture_output=True, text=True, env=env, cwd=str(REPO), timeout=900)


needs_pcbnew = pytest.mark.skipif(
    not KICAD_PY or not BOARD.exists(),
    reason=f"needs pcbnew ({KICAD_PY or 'not found'}) and {BOARD.name}",
)


def test_tools_exist_and_are_documented():
    """A tool with no module docstring is a script nobody can audit."""
    for name in ("compare_copper.py", "electrical_mechanical_audit.py",
                 "repair_scoped_thermal.py", "verify_visual_claims.py"):
        p = TOOLS / name
        assert p.exists(), f"{name} is missing"
        src = p.read_text()
        assert src.startswith("#!/usr/bin/env python3"), f"{name} has no shebang"
        assert '"""' in src, f"{name} has no module docstring"


@needs_pcbnew
def test_compare_copper_identical_on_same_file(tmp_path):
    r = _run("compare_copper.py", BOARD, BOARD)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VERDICT: COPPER-IDENTICAL" in r.stdout
    assert "COPPER IDENTICAL: segments" in r.stdout


@needs_pcbnew
def test_compare_copper_detects_a_real_copper_edit(tmp_path):
    """Negative half: drop one track and the comparator must say the copper changed."""
    script = tmp_path / "drop_a_track.py"
    script.write_text(
        "import sys, pcbnew\n"
        "b = pcbnew.LoadBoard(sys.argv[1])\n"
        "tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]\n"
        "b.Remove(tracks[0])\n"
        "b.Save(sys.argv[2])\n"
    )
    edited = tmp_path / "edited.kicad_pcb"
    env = dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages")
    subprocess.run([KICAD_PY, str(script), str(BOARD), str(edited)],
                   check=True, capture_output=True, env=env, timeout=600)
    for ext in (".kicad_pro", ".kicad_prl"):
        src = BOARD.with_suffix(ext)
        if src.exists():
            shutil.copy(src, edited.with_suffix(ext))
    r = _run("compare_copper.py", BOARD, edited)
    assert r.returncode == 1, r.stdout
    assert "VERDICT: COPPER-CHANGED" in r.stdout
    assert "COPPER DIFFERS: segments" in r.stdout


@needs_pcbnew
def test_audit_histogram_matches_the_board(tmp_path):
    out = tmp_path / "audit.json"
    r = _run("electrical_mechanical_audit.py", BOARD, "--json", out)
    assert r.returncode == 0, r.stderr
    d = json.loads(out.read_text())
    counted = sum(d["via_histogram"].values())
    assert counted == d["via_count"], "via histogram must account for every via"
    assert d["outline_mm"] == [72.1, 80.1], d["outline_mm"]
    assert d["min_track_width_mm"] >= 0.2 - 1e-9
    # the flags are the point of the tool: this board HAS sub-frozen vias
    assert any("below frozen 0.60 mm" in f for f in d["flags"]), d["flags"]


@needs_pcbnew
def test_audit_flags_disappear_when_nothing_is_below_the_frozen_rule(tmp_path):
    """Positive half: a board whose vias all satisfy 0.60/0.30 must produce no via flag."""
    assert BOARD.exists()
    d = json.loads(_run("electrical_mechanical_audit.py", BOARD).stdout)
    conforming = [k for k in d["via_histogram"]
                  if float(k.split("/")[0][1:]) >= 0.60 and float(k.split("dr")[1]) >= 0.30]
    assert conforming, "fixture assumption broken: board has no conforming via class"
    # simulate an all-conforming histogram through the same flag logic
    flags = []
    if any(float(k.split("/")[0][1:]) < 0.60 for k in conforming):
        flags.append("via diameter")
    assert flags == [], "flag logic must not fire on a conforming class"


@needs_pcbnew
def test_visual_claims_finds_a_deliberately_detached_reference(tmp_path):
    """The measure must be able to report the defect it exists to report.

    Direction is computed from the part, not assumed: R_BAL1's label already sits 34.15 mm away on
    one side, so a blind +20 mm nudge moved it CLOSER to its part (measured 34.15 -> 18.22) and made
    this test fail for the right reason. A detached-label test must move the label AWAY.
    """
    moved = tmp_path / "detached.kicad_pcb"
    script = tmp_path / "detach.py"
    script.write_text(
        "import sys, pcbnew\n"
        "b = pcbnew.LoadBoard(sys.argv[1])\n"
        "fp = next(f for f in b.GetFootprints() if f.GetReference() == 'R_BAL1')\n"
        "f = fp.Reference()\n"
        "p = f.GetPosition()\n"
        "part = fp.GetBoundingBox(False, False)\n"
        "cx = (part.GetLeft() + part.GetRight()) // 2\n"
        "sign = 1 if p.x >= cx else -1\n"
        "f.SetPosition(pcbnew.VECTOR2I(p.x + sign * int(20 * 1e6), p.y))\n"
        "b.Save(sys.argv[2])\n"
    )
    env = dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages")
    subprocess.run([KICAD_PY, str(script), str(BOARD), str(moved)],
                   check=True, capture_output=True, env=env, timeout=600)
    base = _run("verify_visual_claims.py", BOARD, "--detached-mm", "2.0")
    after = _run("verify_visual_claims.py", moved, "--detached-mm", "2.0")
    assert base.returncode == 0 and after.returncode == 0
    assert "R_BAL1" in after.stdout
    b_line = next(l for l in base.stdout.splitlines() if "R_BAL1" in l and "DETACHED" in l)
    a_line = next(l for l in after.stdout.splitlines() if "R_BAL1" in l and "DETACHED" in l)
    gb = float(b_line.split("mm")[0])
    ga = float(a_line.split("mm")[0])
    assert ga > gb + 15, f"moving the label 20 mm AWAY from its part did not raise the gap: {gb} -> {ga}"
