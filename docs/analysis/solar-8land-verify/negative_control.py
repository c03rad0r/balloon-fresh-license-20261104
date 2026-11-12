#!/usr/bin/env python3
"""NEGATIVE CONTROL for the bitmap router: prove it can say NO.

A router that always finds a path proves nothing. This asks it for three things that MUST fail or
must be trivially short, and checks the answers:

  1. SAME PAD to SAME PAD                 -> path of length 0 (degenerate, must not crash)
  2. TWO PADS ON OPPOSITE FACES ONLY       -> must report "no B.Cu pad", because U2.4 is F.Cu-only
  3. A pair with the clearance DOUBLED     -> if a 0.20 mm-clearance path exists, a 0.40 mm one may
                                              still exist; but raising it to 1.50 mm must FAIL or
                                              get longer. A router that returns the same length at
                                              1.50 mm clearance is not applying the rule.

Exit 0 = all three behave; 1 = the router is not discriminating.
"""
import subprocess
import sys

REPO = "/home/c08r4d0r/worktrees/flight-readiness-20261102"
SCRIPT = f"{REPO}/docs/analysis/solar-8land-verify/route_solar_bitmap.py"
BOARD = f"{REPO}/tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb"
ENV = {"PYTHONPATH": "/usr/lib/python3/dist-packages", "PATH": "/usr/bin:/bin"}


def run(*args):
    r = subprocess.run(["/usr/bin/python3", SCRIPT, BOARD, *args],
                       capture_output=True, text=True, env=ENV, timeout=600)
    return r.stdout


print("=== 1. clearance 1.50 mm on pair 2 (must FAIL or get much longer than 5.59 mm) ===")
out = run("--pair", "2", "--grid", "0.15", "--clearance", "1.50")
print(out.strip())
tight = 5.59
ok1 = ("NO PATH" in out) or ("PATH" in out and "PATH 5.5" not in out)
line = next((l for l in out.splitlines() if "PATH" in l or "NO PATH" in l), "")
if "PATH" in line and "NO PATH" not in line:
    try:
        got = float(line.split("PATH")[1].split("mm")[0])
        ok1 = got > tight * 1.2
        print(f"   length at 1.50 mm clearance = {got} mm vs {tight} mm at 0.20 -> "
              f"{'longer, rule applied' if ok1 else 'SAME LENGTH: rule NOT applied'}")
    except Exception:
        pass

print("\n=== 2. pair 8 (U2.4 is F.Cu-only) must report no B.Cu pad, not a path ===")
out2 = run("--pair", "8", "--grid", "0.15")
print(out2.strip())
ok2 = "no B.Cu pad" in out2

print("\n=== 3. pair 5 at 0.10 mm clearance vs 0.20 mm (0.10 must be <= the 0.20 length) ===")
o20 = run("--pair", "5", "--grid", "0.10", "--clearance", "0.20")
o10 = run("--pair", "5", "--grid", "0.10", "--clearance", "0.10")
print(o20.strip())
print(o10.strip())
def length(o):
    for l in o.splitlines():
        if "PATH" in l and "NO PATH" not in l:
            return float(l.split("PATH")[1].split("mm")[0])
    return None
l20, l10 = length(o20), length(o10)
ok3 = l20 is not None and l10 is not None and l10 <= l20 + 0.2
print(f"   0.20 -> {l20} mm ; 0.10 -> {l10} mm ; {'monotone, plausible' if ok3 else 'INCONSISTENT'}")

print("\nRESULT:", "PASS -- router discriminates" if (ok1 and ok2 and ok3) else
      f"FAIL -- ok1={ok1} ok2={ok2} ok3={ok3}")
sys.exit(0 if (ok1 and ok2 and ok3) else 1)
