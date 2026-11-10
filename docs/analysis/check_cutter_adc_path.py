"""Bounded DC arithmetic only; not a power-sequencing or component proof."""
from itertools import product

TOL = 0.005
vmax = 5.4 * (1 + TOL) / 2
assert vmax < 3.0 < 3.6
corners = []
for a, b, c, ron in product((0.995, 1.005), (0.995, 1.005),
                            (0.995, 1.005), (0, 4.5)):
    r1, r2, r3 = 1000*a, 1000*b, 10000*c
    parallel = r2 * (ron+r3) / (r2+ron+r3)
    gain = parallel / (r1+parallel) * r3 / (ron+r3)
    corners.append(gain)
    assert 5.4 * gain < 3.0
    assert (5.4 / (r1+parallel))**2*r1 < 0.009
assert 0.473 < min(corners) < max(corners) < 0.479
assert 2e-6 * 10000*1.005 < 0.021
assert 50e-9 * 503 < 25.2e-6
nominal = 10/21
print(f'PASS: DC corners gain={min(corners):.9f}..{max(corners):.9f}')
print(f'PASS: open-switch node max={vmax:.6f} V; off bleed <=20.1 mV')
print(f'25mV signal={0.025*nominal:.9f} V; codes={0.025*nominal/7.8125e-6:.3f}')
print('NOT VERIFIED: rail ramps, component faults, leakage outside table conditions, ADC impedance bound')
