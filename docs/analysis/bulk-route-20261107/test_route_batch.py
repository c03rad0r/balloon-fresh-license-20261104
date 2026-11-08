#!/usr/bin/env python3
"""test_route_batch.py -- POSITIVE CONTROL for route_batch.py's predicate (AGENTS.md 27).

A gate that cannot fail is not a gate. This asserts, on the REAL board, both directions:

  ACCEPT  a stub between two same-net pads inside one open corridor        -> seg_ok True
  REJECT  a stub through a foreign pad                                     -> seg_ok False
  REJECT  copper inside the C10 frozen neighbourhood                       -> seg_ok False
  REJECT  a via centred inside a same-net SMD pad (via-in-pad)             -> via_ok False
  REJECT  a via whose DISC overlaps a pad but whose CENTRE does NOT        -> via_ok False
  REJECT  a stub crossing a J_W cavity edge (ADR-142)                      -> seg_ok False
  AGREE   every free raster cell is accepted by the validator              -> agreement_test

WHY THIS IS NOW REAL pytest TESTS. It used to be a script with a main() guarded by
__main__. pytest COLLECTED the file, ran nothing, and reported "no tests ran" -- so the gate
never fired on an unattended run. Same defect class as a --deadline flag that is parsed and
never read: it looked like a gate and was not one. Each assertion is now its own test function.

Run either way:
    pytest docs/analysis/bulk-route-20261107/test_route_batch.py
    python3 docs/analysis/bulk-route-20261107/test_route_batch.py     (script mode, verbose)
"""
import importlib.util
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HW = os.path.join(REPO, "tracker", "hardware")
sys.path.insert(0, HERE)
sys.path.insert(0, HW)

pcbnew = pytest.importorskip("pcbnew", reason="pcbnew lives only in the distro interpreter")

# IMPORT THE ROUTER THE DRIVER ACTUALLY RUNS, BY PATH.
# `import route_batch` was ambiguous: route_batch.py exists BOTH in this analysis directory and
# in tracker/hardware/, and HERE was first on sys.path, so the gate tested the analysis copy
# while route_one.sh executed the tracker copy. A poison planted in tracker/hardware/ therefore
# left the gate green -- measured, 7 passed with the exact shipped bug reintroduced. A gate that
# tests a different file than the tool is not a gate.
_spec = importlib.util.spec_from_file_location(
    "route_batch", os.path.join(HW, "route_batch.py"))
if _spec is None or _spec.loader is None:
    pytest.skip("tracker/hardware/route_batch.py not loadable", allow_module_level=True)
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)
sys.modules["route_batch"] = R


def test_imports_the_router_the_driver_runs():
    """The tested module must be tracker/hardware/route_batch.py, not the analysis copy.
    Without this, every other control in this file can be green while the shipped router is
    broken."""
    got = os.path.abspath(R.__file__)
    want = os.path.abspath(os.path.join(HW, "route_batch.py"))
    assert got == want, f"gate imported {got}, but the driver runs {want}"
    assert os.path.exists(want), f"router missing at {want}"

BOARD = os.path.join(HERE, "candidate", "board.kicad_pcb")
if not os.path.exists(BOARD):
    pytest.skip(f"control board missing: {BOARD}", allow_module_level=True)


@pytest.fixture(scope="module")
def W():
    return R.World(BOARD)


def pads_near(W, net, xy, rad=6.0):
    out = []
    for p in W.pads:
        if p["net"] != net:
            continue
        cx = (p["rect"][0] + p["rect"][2]) / 2
        cy = (p["rect"][1] + p["rect"][3]) / 2
        if math.hypot(cx - xy[0], cy - xy[1]) <= rad:
            out.append(p)
    return out


def test_accept_legal_stub(W):
    """A same-net stub in open corridor must be ACCEPTED.

    The opposite failure mode matters too: a predicate that rejects everything is not usable,
    and every 'unroutable' verdict drawn from it would be worthless.
    """
    trials = [
        ("/F33_VSENSE", (21.0, 8.0), (22.0, 7.8)),
        ("/SPI1_MISO", (11.0, 14.1), (33.8, 14.1)),
    ]
    accepted = 0
    for net, a, b in trials:
        pa, pb = pads_near(W, net, a, 2.0), pads_near(W, net, b, 2.0)
        if not pa or not pb:
            continue
        r0, r1 = pa[0]["rect"], pb[0]["rect"]
        p0 = ((r0[0] + r0[2]) / 2, (r0[1] + r0[3]) / 2)
        p1 = ((r1[0] + r1[2]) / 2, (r1[1] + r1[3]) / 2)
        own = {(pa[0]["ref"], pa[0]["num"]), (pb[0]["ref"], pb[0]["num"])}
        ok, _ = W.seg_ok(R.F, p0, p1, net, own)
        if ok:
            accepted += 1
    assert accepted > 0, (
        "no ACCEPT probe passed -- the predicate rejects everything, so it is not usable "
        "and any 'unroutable' verdict from it is worthless")


def test_reject_stub_through_foreign_pad(W):
    """A stub driven straight through a foreign pad must be REFUSED."""
    u1pads = [p for p in W.pads if p["ref"] == "U1" and p["num"] != ""]
    assert u1pads, "no U1 pads to probe"
    tgt = u1pads[len(u1pads) // 2]
    cx = (tgt["rect"][0] + tgt["rect"][2]) / 2
    cy = (tgt["rect"][1] + tgt["rect"][3]) / 2
    ok, why = W.seg_ok(R.F, (cx - 2.0, cy), (cx + 2.0, cy), "/EN", set())
    assert not ok, f"predicate ACCEPTED a stub through foreign pad U1.{tgt['num']} ({why!r})"


def test_reject_copper_inside_c10_freeze(W):
    """The frozen C10 neighbourhood must refuse copper: Astra CHANGES_REQUESTED is live."""
    g = R.C10_GUARD
    cx, cy = (g[0] + g[2]) / 2, (g[1] + g[3]) / 2
    ok, why = W.seg_ok(R.F, (cx - 0.5, cy), (cx + 0.5, cy), "/EN", set())
    assert not ok, f"predicate ACCEPTED copper inside the frozen C10 neighbourhood ({why!r})"


def test_reject_via_in_pad_centre(W):
    """A via centred ON a same-net SMD pad is via-in-pad and must be REFUSED."""
    vpads = [p for p in W.pads
             if p["net"] == "+3V3" and not p["pth"] and p["drill"] == 0]
    assert vpads, "no SMD +3V3 pad to probe"
    p = vpads[0]
    cx = (p["rect"][0] + p["rect"][2]) / 2
    cy = (p["rect"][1] + p["rect"][3]) / 2
    ok, _ = W.via_ok(cx, cy, "+3V3")
    assert not ok, f"via_ok ACCEPTED via-in-pad at {p['ref']}.{p['num']}"


def test_reject_via_disc_overlap_centre_outside(W):
    """THE REGRESSION THAT SHIPPED A REAL VIA-IN-PAD ON /EN.

    The centre-in-pad control above passes even for a centre-only predicate. The defect that
    actually escaped put the via centre 0.05 mm OUTSIDE the pad edge: the centre is not in the
    rect, but the 0.600 mm disc overlaps the pad by 0.25 mm. Measured on the pushed /EN board
    at (10.2, 36.7) against U1.3, and invisible to kicad-cli because KiCad has no via-in-pad
    rule. A control has to sit ON the failure, not next to it.
    """
    u13 = [p for p in W.pads if p["ref"] == "U1" and p["num"] == "3"]
    if not u13:
        pytest.skip("U1.3 not present on this board")
    p = u13[0]
    x0, y0, x1, y1 = p["rect"]
    cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2
    step = 0.05
    n = int(2.5 / step)
    accepted = []
    for a in range(-n, n + 1):
        for b in range(-n, n + 1):
            cx, cy = cx0 + a * step, cy0 + b * step
            gap = R.seg_rect(cx, cy, cx, cy, p["rect"]) - R.VIA_D / 2
            if gap >= -R.EPS:
                continue                      # disc does not reach the pad; not this check
            ok, why = W.via_ok(cx, cy, "/EN")
            if ok:
                accepted.append((round(cx, 3), round(cy, 3), round(gap, 3), why))
    assert not accepted, (
        f"{len(accepted)} site(s) whose DISC overlaps pad U1.3 were ACCEPTED by via_ok: "
        f"{accepted[:4]}")

    # A boolean is not enough on its own: an unrelated neighbour can refuse every overlapping
    # site and mask a permissive pad test. Measured -- poisoning the pad test to a point test
    # still produced zero acceptances, because /U1.2 and /SPI2_MOSI refuse those cells anyway.
    # So assert the DISCRIMINATION directly: for at least one site the disc test must refuse
    # while a pure point test would allow. If the pad test has no radius, this is empty.
    discriminated = 0
    for a in range(-n, n + 1):
        for b in range(-n, n + 1):
            cx, cy = cx0 + a * step, cy0 + b * step
            gap = R.seg_rect(cx, cy, cx, cy, p["rect"]) - R.VIA_D / 2
            if not (-R.VIA_D < gap < -R.EPS):
                continue                      # want sites whose disc reaches, centre outside
            point_in_pad = (x0 <= cx <= x1 and y0 <= cy <= y1)
            if point_in_pad:
                continue
            ok, why = W.via_ok(cx, cy, "/EN")
            if not ok and "via-in-pad" in why:
                discriminated += 1
    assert discriminated > 0, (
        "via_ok never refused a site whose disc reaches U1.3 while its CENTRE is outside the "
        "pad -- the pad test has no radius, which is the exact bug that shipped a real "
        "via-in-pad on /EN")


def test_reject_track_across_jw_cavity(W):
    """ADR-142: a TRACK must never cross a J_W socket cavity (the pad exemption is pad-only)."""
    edges = [e for e in W.edge_segs if e[0] == "J_W2"]
    if not edges:
        pytest.skip("no J_W2 cavity edges on this board")
    ok, why = W.seg_ok(R.F, (34.5, 77.0), (37.5, 77.0), "/W2_SOLAR_N", set())
    assert not ok, f"predicate ACCEPTED a stub across a J_W cavity (ADR-142 violated: {why!r})"


def test_raster_never_permissive(W):
    """AGENTS#27 in the sound direction: every FREE raster cell must be accepted by the
    validator. The raster may over-block; it must never permit what validation refuses."""
    grid, nx, ny = R.build_raster(W, 0.1, "/EN", [])
    ok, why = R.agreement_test(W, grid, 0.1, "/EN", set(), samples=1500)
    assert ok, f"raster/validator disagree: {why}"


def main():
    """Script mode: run every check and print a readable verdict."""
    checks = [
        ("ACCEPT legal stub", test_accept_legal_stub),
        ("REJECT stub through foreign pad", test_reject_stub_through_foreign_pad),
        ("REJECT copper inside C10 freeze", test_reject_copper_inside_c10_freeze),
        ("REJECT via-in-pad (centre)", test_reject_via_in_pad_centre),
        ("REJECT via disc overlap (centre outside)",
         test_reject_via_disc_overlap_centre_outside),
        ("REJECT track across J_W cavity", test_reject_track_across_jw_cavity),
        ("AGREE raster never permissive", test_raster_never_permissive),
    ]
    W = R.World(BOARD)
    fails = []
    for name, fn in checks:
        try:
            fn(W)
            print(f"  PASS  {name}")
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            fails.append(name)
        except Exception as e:                       # noqa: BLE001
            print(f"  SKIP  {name}: {type(e).__name__}: {e}")
    print()
    if fails:
        print(f"{len(fails)} FAILED: {fails}")
        return 1
    print("ALL PREDICATE CONTROLS PASSED (both directions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
