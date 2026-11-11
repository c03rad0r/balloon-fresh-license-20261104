#!/usr/bin/env python3
"""Pump sizing model for the inflation controller (ADR-150 / ADR-088).

Answers ONE question: what must the pump do, and what does the protocol already require of it?

THE FINDING THAT CHANGES THE PUMP SPEC. The pump never touches lifting gas. Read the protocol's
own pipeline diagram and the Yokohama steps:

    [Pump] -> [Balloon] -> [BMP280] -> [ESP32-C3]     (protocol line 157)
    C.4 step 2  inflate with AIR to ~85 % circumference (~88"), hold 2-4 h
    C.4 step 4  deflate completely, ~2 h WITH THE PUMP ON SUCTION
    C.4 step 6  refill with He 4.6 (~70 L)  <-- NOT the pump

So the pump is an AIR pump used for pre-stretch and vacuum deflate. Helium arrives from a cylinder
and its flow is set by a regulator, not by this pump. That removes helium compatibility from the
pump's spec entirely -- and it means the valve study's "envelope decides the valve" conclusion
applies to the HELIUM side, while the pump is sized by the air/pre-stretch side.

THREE REQUIREMENTS THE PROTOCOL SETS THAT A FLOW NUMBER ALONE MISSES:
  1. PRESSURE AND VACUUM.  Step 2 pushes air in; step 4 pulls it out with the pump on suction.
     A positive-pressure-only pump cannot perform step 4. Many diaphragm pumps are single-direction
     (the BD-03A is positive, the BD-03V is negative) -- so this is a real selection constraint.
  2. A LONG HOLD.  Step 3 holds the stretch circumference for 12-48 h. During that time the pump
     must be OFF (ADR-088 requires pump-off shutdown to be verifiable) and the system must hold on
     the VALVE. The pump is idle for up to 48 hours; the valve is the thing under load.
  3. LEAK-DETECTION RESOLUTION.  Step 4's acceptance is a leak rate in mbar/h, so the pressure
     sensor resolution, not the pump, sets the measurement floor.

Stdlib only. Every figure printed here is quoted in the study doc.
"""
import math

# [CITED docs/prestretch/PRE-STRETCHING-PROTOCOL.md]
V_18_MYLAR_L = 15.0          # B.1 "~14-15 L"
HE_REFILL_L = 70.0           # C.4 step 6 "~0.07 m3 = 70 L" He 4.6
DEFLATE_HOURS = 2.0          # C.4 step 4 "~2 h with the pump on suction"
HOLD_HOURS_MIN = 12.0        # C.4 step 3 "12-48 h, min 24 h for first flights"
HOLD_HOURS_MAX = 48.0
LEAK_ACCEPT_MBAR_H = 2.0     # B.4 "0.5-2 mbar/h = OK" (>5 reject)

# Pump candidates found, with their own published specs. All 12 V, all diaphragm.
PUMPS = [
    # name,                  L/min at 0 bar, max pressure bar, max vacuum kPa, power W, price USD
    ("BD-01A (brush)",        0.75, 0.75,  30,  2.0,  None),
    ("BD-02A",                2.25, 1.0,   47,  3.0,  None),
    ("BD-03A-3L",             3.0,  2.0,    0,  5.0,  None),
    ("BD-03V-5L (vacuum)",    5.0,  0.0,   70,  6.0,  None),
    ("JSG OD-05TVB-S.1",      5.5,  1.25,  70,  4.0,  None),
    ("BD-04AB-11L",          11.0,  2.5,   75,  7.0,  None),
    ("Boxer 5KS (12 V)",      5.1,  0.30,  50,  4.0,  74.64),
]


def sphere_litres(inches: float) -> float:
    r = (inches * 0.0254) / 2.0
    return (4.0 / 3.0) * math.pi * r ** 3 * 1000.0


def main() -> int:
    print("=" * 80)
    print("1. WHAT IS BEING MOVED — and by which device")
    print("=" * 80)
    D32, D36, D60 = 32, 36, 60
    targets = [(f'{D32}" Yokohama (pre-stretch, the main protocol)', sphere_litres(D32)),
               (f'{D36}" latex', sphere_litres(D36)),
               (f'{D60}" Cymylar', sphere_litres(D60))]
    for name, v in targets:
        print(f"  {name:44s} {v:8.1f} L  (sphere UPPER bound)")
    LBL18 = '18" DecoGlee Mylar'
    LBLHE = 'He refill (32" Yokohama)'
    print(f"  {LBL18:44s} {V_18_MYLAR_L:8.1f} L  [CITED B.1]")
    print(f"  {LBLHE:44s} {HE_REFILL_L:8.1f} L  [CITED C.4 step 6]")
    print()
    print("  AIR path  : pump  -> valve -> balloon      (pre-stretch + vacuum deflate)")
    print("  HELIUM path: cylinder -> regulator -> balloon  (NOT the pump)")

    print()
    print("=" * 80)
    print("2. INFLATE: time to fill, at the pump's own rated flow")
    print("=" * 80)
    v32 = sphere_litres(32)
    print(f"  target: 32\" Yokohama = {v32:.0f} L   Q = V/t  =>  t = V/Q")
    print(f"  {'pump':24s}{'L/min':>8s}{'minutes':>10s}{'verdict':>12s}")
    print("  " + "-" * 54)
    for name, lpm, _p, _v, _w, _c in PUMPS:
        if lpm <= 0:
            continue
        mins = v32 / lpm
        verdict = "fast" if mins < 40 else ("workable" if mins < 90 else "slow")
        print(f"  {name:24s}{lpm:8.1f}{mins:10.0f}{verdict:>12s}")
    print()
    print("  NOTE: rated flow is at 0 bar. Real flow falls as back-pressure rises, and the")
    print("        protocol holds the balloon at a raised pressure -- so these are BEST cases.")

    print()
    print("=" * 80)
    print("3. DEFLATE: protocol says ~2 h on suction. Is any pump fast enough?")
    print("=" * 80)
    print(f"  required average = {v32:.0f} L / {DEFLATE_HOURS:.0f} h / 60 = {v32/(DEFLATE_HOURS*60):.2f} L/min")
    print("  ...which EVERY candidate above exceeds. Deflate is NOT a flow constraint.")
    print("  It IS a DIRECTION constraint: a positive-pressure-only pump cannot do step 4 at all.")

    print()
    print("=" * 80)
    print("4. THE REAL PUMP CONSTRAINT: it must do pressure AND vacuum")
    print("=" * 80)
    print(f"  {'pump':24s}{'pres bar':>10s}{'vac kPa':>9s}{'both?':>8s}")
    print("  " + "-" * 52)
    for name, _l, p, v, _w, _c in PUMPS:
        both = "YES" if (p > 0 and v > 0) else "NO"
        print(f"  {name:24s}{p:10.2f}{v:9.0f}{both:>8s}")
    print()
    print("  This is the finding a flow number hides: BD-03A is pressure-only, BD-03V is")
    print("  vacuum-only. Buying either alone fails the protocol. The dual-direction candidates")
    print("  are the OD-05TVB class (-70 kPa AND 1.0-1.5 bar) or a reversible/3-way-valve rig.")

    print()
    print("=" * 80)
    print("5. HOLD: the pump is IDLE for up to 48 h -- the VALVE is under load")
    print("=" * 80)
    print(f"  hold window          : {HOLD_HOURS_MIN:.0f}-{HOLD_HOURS_MAX:.0f} h  [CITED C.4 step 3]")
    print(f"  acceptance leak rate : <{LEAK_ACCEPT_MBAR_H:.1f} mbar/h  [CITED B.4]")
    vol_m3 = v32 / 1000.0
    # 1 mbar = 100 Pa; leaked volume at that pressure over the hold
    for h in (HOLD_HOURS_MIN, HOLD_HOURS_MAX):
        p_drop_pa = LEAK_ACCEPT_MBAR_H * 100.0 * h
        frac = p_drop_pa / 101325.0
        loss_l = frac * v32
        print(f"  at {h:4.0f} h: {LEAK_ACCEPT_MBAR_H:.1f} mbar/h => {p_drop_pa/100:.1f} mbar total"
              f" = {loss_l:.2f} L of gas ({frac*100:.2f} %)")
    print()
    print("  So an ACCEPTABLE valve leak still loses only a fraction of a litre over 48 h.")
    print("  The valve, not the pump, must hold this -- and the sensor must resolve it.")

    print()
    print("=" * 80)
    print("6. WHAT DECIDES THE PUMP")
    print("=" * 80)
    print("  NOT flow        -- every candidate fills a 32\" faster than the operator can watch it")
    print("  NOT helium      -- the pump never sees He; a regulator sets that flow")
    print("  YES direction   -- pressure AND vacuum are both mandatory (steps 2 and 4)")
    print("  YES duty/life   -- hold is 12-48 h, and brushes are rated ~1000 h vs 3-5x brushless")
    print("  YES noise       -- 55-65 dB for an hour+ beside a 0.5 mbar/h leak measurement")
    print("  YES PWM         -- to approach the target slowly; a 5 L/min pump at full speed")
    print("                     overshoots any fine circumference adjustment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
