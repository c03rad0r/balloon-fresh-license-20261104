#!/usr/bin/env python3
"""Valve sizing model for the merged inflation/tracking control board (ADR-150).

Answers ONE question: what flow must the fill valve pass, and is the candidate valve right?

WHY THIS EXISTS. ADR-150 names the fill valve as the #1 open blocker and the BOM lists the SMC
VQZ1121 as a CANDIDATE, because coil voltage, "normally closed" and helium behaviour were all
unverified. Sizing it by intuition is how you either buy a $45 valve that cannot fill a 60" balloon,
or one so oversized that the fill rate cannot be controlled.

WHAT IS KNOWN AND WHAT IS NOT.
  KNOWN (cited): the 18" DecoGlee Mylar holds 14-15 L of gas (PRE-STRETCHING-PROTOCOL.md B.1).
  DERIVED (computed): 36" and 60" envelope volumes as spheres -- an UPPER bound, since real
    foil balloons are pillow-shaped and hold less than a sphere of the same nominal size.
  UNKNOWN: the target/ramp/dwell/max differential pressure. ADR-088 SS3 makes these UNKNOWN PER
    ENVELOPE and withdraws every numeric pressure instruction. This model therefore never assumes
    a setpoint; it reports required FLOW for a chosen fill TIME, which is a requirement the operator
    can actually pick, and labels the pressure as a parameter.

Stdlib only. Every figure printed by this script is quoted in the study doc.
"""
import math

# ---------------------------------------------------------------- constants with provenance
# [CITED docs/PRE-STRETCHING-PROTOCOL.md B.1] "Gas volume: ~14-15 L" for the 18" DecoGlee Mylar
V_18_MYLAR_L = 15.0

# Nominal sizes from docs/balloon-flight-lessons.md (36" latex, 60" Cymylar)
ENVELOPES = [
    ("18\" DecoGlee Mylar", V_18_MYLAR_L, "cited 14-15 L"),
    ("36\" latex", None, "computed sphere"),
    ("60\" Cymylar", None, "computed sphere"),
]


def sphere_litres(diameter_in: float) -> float:
    """Volume of a sphere, in litres. Upper bound for a foil balloon of that nominal size."""
    r_m = (diameter_in * 0.0254) / 2.0
    return (4.0 / 3.0) * math.pi * r_m ** 3 * 1000.0


def main() -> int:
    print("=" * 78)
    print("ENVELOPE VOLUME — what the valve must move")
    print("=" * 78)
    vols = []
    for name, v, basis in ENVELOPES:
        if v is None:
            inches = float(name.split('"')[0])
            v = sphere_litres(inches)
            basis = f"computed sphere, r={inches*0.0254/2:.4f} m (UPPER bound)"
        vols.append((name, v, basis))
        print(f"  {name:22s} {v:9.2f} L   {basis}")

    vmin = min(v for _, v, _ in vols)
    vmax = max(v for _, v, _ in vols)
    print(f"\n  range: {vmin:.1f} L .. {vmax:.1f} L   ratio {vmax/vmin:.1f}x")

    print()
    print("=" * 78)
    print("REQUIRED AVERAGE FLOW vs FILL TIME  (Q = V / t)")
    print("=" * 78)
    print(f"  {'envelope':24s}" + "".join(f"{t:>14s}" for t in ("30 s", "120 s", "10 min")))
    print("  " + "-" * 74)
    for name, v, _ in vols:
        row = f"  {name:24s}"
        for t in (30.0, 120.0, 600.0):
            q_lpm = v / (t / 60.0)          # litres per minute
            row += f"{q_lpm:9.2f} L/min" .rjust(14)
        print(row)

    print()
    print("  NOTE: this is AVERAGE flow. A valve must pass the PEAK, and the pump sets the")
    print("        achievable rate -- the valve only has to not restrict it.")

    print()
    print("=" * 78)
    print("IS THE CANDIDATE VALVE OVERSIZED?")
    print("=" * 78)
    # SMC VQZ1121: Cv ~0.19 (A/B to EA/EB) per the vendor spec sheet quoted in the BOM.
    # Cv is US gpm of WATER at 1 psi drop. Convert to litre/min water, then scale to gas with the
    # standard sonic-flow relation for air at a supply pressure. Both conversions are shown so the
    # reader can reject them if they disagree with their own reference.
    Cv = 0.19
    water_lpm_per_psi = Cv * 3.78541          # 1 US gpm = 3.78541 L/min
    print(f"  SMC VQZ1121 quoted Cv          : {Cv}")
    print(f"  = water flow at 1 psi drop     : {water_lpm_per_psi:.3f} L/min (water)")
    # Sonic air flow for a valve roughly: Q_air(L/min) ~ 1000 * Cv * P1(bar abs) when choked.
    # Use P1 = 2 bar abs (a 1 bar supply) -> generous to the valve.
    q_air_sonic = 1000.0 * Cv * 2.0
    print(f"  = air, sonic, at 2 bar abs     : ~{q_air_sonic:.0f} L/min (gas, order-of-magnitude)")
    print()
    q_need_18 = vmin / (120.0 / 60.0)
    print(f"  18\" balloon, 120 s fill needs  : {q_need_18:8.2f} L/min")
    print(f"  valve air capability (est)     : {q_air_sonic:8.0f} L/min")
    print(f"  => oversizing factor           : {q_air_sonic/q_need_18:8.0f}x")

    print()
    print("  CONCLUSION ON FLOW: the valve is not flow-limited for a pico balloon. The 18\" case")
    print("  needs single-digit L/min and the candidate passes orders of magnitude more. That is")
    print("  an argument for a SMALLER, cheaper direct-acting valve, not a bigger one -- and a")
    print("  grossly oversized valve makes controlled ramp-rate harder, not easier.")

    print()
    print("=" * 78)
    print("WHAT THE MODEL CANNOT ANSWER")
    print("=" * 78)
    print("  1. DP targets remain UNKNOWN per ADR-088 SS3 -- no setpoint is assumed here.")
    print("  2. 36\"/60\" volumes are SPHERE UPPER BOUNDS; real foil balloons hold less.")
    print("  3. Helium leaks through small clearances faster than air; gas flow above is air.")
    print("  4. Pump capability is not in the repo, so achievable fill time is unproven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
